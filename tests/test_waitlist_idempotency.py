from pathlib import Path

from app.agents.booking_agent import BookingAgent
from app.agents.message import ACLMessage, Performative
from app.agents.waitlist_agent import WaitlistAgent


class RecordingBus:
    def __init__(self, response=None):
        self.response = response
        self.sent_messages = []

    def send(self, message):
        self.sent_messages.append(message)
        return self.response or message


def test_waitlist_agent_returns_booking_response_without_rerouting():
    bus = RecordingBus()
    agent = WaitlistAgent("WaitlistAgent", bus)
    response = ACLMessage(
        sender="BookingAgent",
        receiver="WaitlistAgent",
        performative=Performative.AGREE,
        content={"booking_id": 25, "idempotent": True}
    )

    assert agent.receive_message(response) is response
    assert bus.sent_messages == []


def test_booking_agent_supports_waitlist_idempotent_insert():
    source = Path("app/agents/booking_agent.py").read_text()

    assert "ON CONFLICT (waitlist_id)" in source
    assert "WHERE waitlist_id IS NOT NULL" in source
    assert '"idempotent": True' in source


def test_migration_preserves_existing_waitlist_statuses():
    migration = Path(
        "database/migrations/001_waitlist_idempotency.sql"
    ).read_text()

    for status in (
        "WAITING",
        "OFFERED",
        "ACCEPTED",
        "FULFILLED",
        "EXPIRED",
        "CANCELLED"
    ):
        assert f"'{status}'" in migration

    assert "bookings_waitlist_id_unique" in migration
    assert "waitlist_active_user_event_unique" in migration
    assert "payments" not in migration
