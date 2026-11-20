import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app import database
from app import main
from app.agents.message import Performative
from app.agents.message import ACLMessage


class FakeMessageBus:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)
        return ACLMessage(
            sender="WaitlistAgent",
            receiver=message.sender,
            performative=Performative.AGREE,
            conversation_id=message.conversation_id,
            content={
                "success": True,
                "expired_count": 2
            }
        )


def test_vercel_environment_disables_local_scheduler(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")

    assert main.is_vercel_environment() is True


def test_waitlist_cron_requires_secret(monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)

    with pytest.raises(HTTPException) as error:
        main.trigger_waitlist_expiry(None)

    assert error.value.status_code == 503


def test_waitlist_cron_routes_expiry_message(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    bus = FakeMessageBus()
    monkeypatch.setattr(
        main.app.state,
        "agent_runtime",
        {"message_bus": bus},
        raising=False
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="test-cron-secret"
    )
    response = main.trigger_waitlist_expiry(credentials)

    assert response["status"] == "completed"
    assert response["expired_count"] == 2
    assert len(bus.messages) == 1
    assert bus.messages[0].content["action"] == "EXPIRE_WAITLIST"


def test_neon_ssl_is_required_in_vercel(monkeypatch):
    captured = {}

    def fake_connect(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("PGPASSWORD", "test-database-secret")
    monkeypatch.delenv("PGSSLMODE", raising=False)
    monkeypatch.setattr(database.psycopg, "connect", fake_connect)

    database.get_db_connection()

    assert captured["sslmode"] == "require"
