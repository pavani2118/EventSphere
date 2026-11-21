import os

import pytest

from app.database import get_db_connection
from app.agents.message import ACLMessage, Performative
from app.agents.waitlist_agent import WaitlistAgent
import app.agents.waitlist_agent as waitlist_module


class FakeMessageBus:

    def __init__(self):
        self.sent_messages = []

    def send(self, message):
        self.sent_messages.append(message)
        return message


class NonCommittingConnection:
    """
    Allows the agent to use a connection without committing
    the test transaction when its context manager exits.
    """

    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self):
        return self.connection.cursor()


@pytest.mark.integration
def test_expire_waitlist_updates_only_old_entries(monkeypatch):

    test_ids = []
    test_connection = None

    if not os.getenv("EVENTSPHERE_TEST_DATABASE"):
        pytest.skip("Set EVENTSPHERE_TEST_DATABASE=1 only for an isolated test database.")

    try:
        # Find a published event and two active attendees who do not already
        # have an active waitlist row for that event.
        with get_db_connection() as setup_connection:
            with setup_connection.cursor() as cursor:
                cursor.execute("""
                    WITH eligible AS (
                        SELECT
                            e.id AS event_id,
                            u.id AS user_id,
                            ROW_NUMBER() OVER (
                                PARTITION BY e.id
                                ORDER BY u.id
                            ) AS attendee_number
                        FROM events e
                        CROSS JOIN users u
                        WHERE e.status = 'PUBLISHED'
                          AND u.role = 'ATTENDEE'
                          AND u.is_active = TRUE
                          AND NOT EXISTS (
                              SELECT 1
                              FROM waitlist w
                              WHERE w.user_id = u.id
                                AND w.event_id = e.id
                                AND w.status = 'WAITING'
                          )
                    )
                    SELECT
                        event_id,
                        MAX(user_id) FILTER (
                            WHERE attendee_number = 1
                        ) AS first_attendee_id,
                        MAX(user_id) FILTER (
                            WHERE attendee_number = 2
                        ) AS second_attendee_id
                    FROM eligible
                    GROUP BY event_id
                    HAVING COUNT(*) >= 2
                    ORDER BY event_id
                    LIMIT 1
                """)
                fixture = cursor.fetchone()

                if not fixture:
                    pytest.skip(
                        "Two eligible active attendees for a published "
                        "event are required."
                    )

                cursor.execute("""
                    INSERT INTO waitlist (
                        user_id, event_id, quantity, status, created_at
                    )
                    VALUES
                        (%s, %s, 1, 'WAITING',
                         NOW() - INTERVAL '8 days'),
                        (%s, %s, 1, 'WAITING', NOW())
                    RETURNING id, created_at
                """, (
                    fixture["first_attendee_id"],
                    fixture["event_id"],
                    fixture["second_attendee_id"],
                    fixture["event_id"]
                ))
                inserted_rows = cursor.fetchall()
                old_row = min(
                    inserted_rows,
                    key=lambda row: row["created_at"]
                )
                recent_row = max(
                    inserted_rows,
                    key=lambda row: row["created_at"]
                )
                old_id = old_row["id"]
                recent_id = recent_row["id"]
                test_ids = [old_id, recent_id]

        # Run the expiry operation in a transaction. Its changes are rolled
        # back before cleanup, so existing records are never persisted as
        # modified by this test.
        test_connection = get_db_connection()
        connection_wrapper = NonCommittingConnection(test_connection)

        monkeypatch.setattr(
            waitlist_module,
            "get_db_connection",
            lambda: connection_wrapper
        )

        agent = WaitlistAgent(
            "WaitlistAgent",
            FakeMessageBus()
        )

        monkeypatch.setattr(
            agent,
            "save_state",
            lambda: None
        )

        message = ACLMessage(
            sender="BookingAgent",
            receiver="WaitlistAgent",
            performative=Performative.REQUEST,
            content={
                "action": "EXPIRE_WAITLIST"
            }
        )

        response = agent.receive_message(message)

        assert response.performative == Performative.AGREE
        assert response.content["success"] is True
        assert response.content["expired_count"] >= 1

        with test_connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, status
                FROM waitlist
                WHERE id = ANY(%s)
                ORDER BY id
            """, (test_ids,))
            results = cursor.fetchall()

        statuses = {
            row["id"]: row["status"]
            for row in results
        }

        assert len(statuses) == 2
        assert statuses[old_id] == "EXPIRED"
        assert statuses[recent_id] == "WAITING"

    finally:
        if test_connection is not None:
            test_connection.rollback()
            test_connection.close()

        if test_ids:
            # Delete only rows inserted by this test.
            with get_db_connection() as cleanup_connection:
                with cleanup_connection.cursor() as cursor:
                    cursor.execute("""
                        DELETE FROM waitlist
                        WHERE id = ANY(%s)
                    """, (test_ids,))
