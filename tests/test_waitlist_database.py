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

    if not os.getenv("PGPASSWORD"):
        pytest.skip("PostgreSQL environment variables are not configured.")

    # Find existing valid foreign-key records.
    with get_db_connection() as setup_connection:

        with setup_connection.cursor() as cursor:

            cursor.execute("""
                SELECT id
                FROM users
                WHERE role = 'ATTENDEE'
                  AND is_active = TRUE
                LIMIT 1
            """)

            attendee = cursor.fetchone()

            cursor.execute("""
                SELECT id
                FROM events
                WHERE status = 'PUBLISHED'
                LIMIT 1
            """)

            event = cursor.fetchone()

            if not attendee or not event:
                pytest.skip(
                    "An active attendee and published event are required."
                )

            # Create one old and one recent waitlist entry.
            cursor.execute("""
                INSERT INTO waitlist (
                    user_id, event_id, quantity, status, created_at
                )
                VALUES
                    (%s, %s, 1, 'WAITING',
                     NOW() - INTERVAL '8 days'),
                    (%s, %s, 1, 'WAITING', NOW())
                RETURNING id
            """, (
                attendee["id"],
                event["id"],
                attendee["id"],
                event["id"]
            ))

            inserted_rows = cursor.fetchall()
            test_ids = [row["id"] for row in inserted_rows]

    # Open a transaction for the agent operation.
    test_connection = get_db_connection()

    try:

        connection_wrapper = NonCommittingConnection(
            test_connection
        )

        # Replace the agent's connection function.
        monkeypatch.setattr(
            waitlist_module,
            "get_db_connection",
            lambda: connection_wrapper
        )

        bus = FakeMessageBus()

        agent = WaitlistAgent(
            "WaitlistAgent",
            bus
        )

        # Prevent writing agent state outside this test transaction.
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
        assert response.content["expired_count"] == 1

        # Check both database records.
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

        assert statuses[test_ids[0]] == "EXPIRED"
        assert statuses[test_ids[1]] == "WAITING"

    finally:

        # Roll back the agent's database changes.
        test_connection.rollback()
        test_connection.close()

        # Remove only the test records.
        with get_db_connection() as cleanup_connection:

            with cleanup_connection.cursor() as cursor:

                cursor.execute("""
                    DELETE FROM waitlist
                    WHERE id = ANY(%s)
                """, (test_ids,))