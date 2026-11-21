from fastapi.testclient import TestClient
from types import SimpleNamespace
from fastapi import HTTPException

import pytest

from app.main import app
import app.dependencies as dependencies_module
import app.bookings as bookings_module
import app.notifications as notifications_module
import app.ticket as ticket_module
import app.venue_hire as venue_hire_module
from app.agents.message import ACLMessage, Performative


client = TestClient(app)


class FakeBookingBus:
    def send(self, message):
        assert isinstance(message, ACLMessage)
        assert message.receiver == "BookingAgent"
        return ACLMessage(
            sender="BookingAgent",
            receiver="BookingAPI",
            performative=Performative.AGREE,
            conversation_id=message.conversation_id,
            content={
                "booking_id": 42,
                "payment_reference": "TEST-PAYMENT",
                "total_amount": "20000.00"
            }
        )


def test_attendee_can_create_booking_with_bearer_token(monkeypatch):
    monkeypatch.setattr(
        dependencies_module,
        "get_user_from_token",
        lambda token: (
            {"id": 184, "role": "ATTENDEE"}
            if token == "valid-attendee-token"
            else (_ for _ in ()).throw(
                HTTPException(
                    status_code=401,
                    detail="Invalid or expired access token"
                )
            )
        )
    )

    with client:
        app.state.agent_runtime = {
            "message_bus": FakeBookingBus()
        }
        response = client.post(
            "/bookings/",
            headers={"Authorization": "Bearer valid-attendee-token"},
            json={
                "event_id": 1,
                "category_id": 2,
                "quantity": 2
            }
        )

    assert response.status_code == 201
    assert response.json()["booking_id"] == 42


def test_logged_out_attendee_cannot_create_booking():
    response = client.post(
        "/bookings/",
        json={
            "event_id": 1,
            "category_id": 2,
            "quantity": 1
        }
    )

    assert response.status_code == 401


def test_expired_attendee_token_cannot_create_booking(monkeypatch):
    def reject_expired_token(token):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token"
        )

    monkeypatch.setattr(
        dependencies_module,
        "get_user_from_token",
        reject_expired_token
    )

    response = client.post(
        "/bookings/",
        headers={"Authorization": "Bearer expired-token"},
        json={
            "event_id": 1,
            "category_id": 2,
            "quantity": 1
        }
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired access token"


def test_admin_cannot_use_attendee_booking_role(monkeypatch):
    monkeypatch.setattr(
        dependencies_module,
        "get_user_from_token",
        lambda token: {"id": 10, "role": "ADMIN"}
    )

    response = client.post(
        "/bookings/",
        headers={"Authorization": "Bearer valid-admin-token"},
        json={
            "event_id": 1,
            "category_id": 2,
            "quantity": 1
        }
    )

    assert response.status_code == 403


def test_event_details_booking_sends_bearer_token():
    with open(
        "app/static/js/event-details.js",
        "r",
        encoding="utf-8"
    ) as script_file:
        script = script_file.read()

    assert '"Authorization"' in script
    assert "`Bearer ${token}`" in script
    assert 'localStorage.getItem("access_token")' in script
    assert 'fetch("/bookings/"' in script
    assert 'window.location.href = "/ui/my-bookings"' in script
    assert 'Your login session has expired' in script


def test_login_preserves_safe_booking_return_url():
    with open(
        "app/static/js/app.js",
        "r",
        encoding="utf-8"
    ) as script_file:
        script = script_file.read()

    assert 'new URLSearchParams(window.location.search).get("next")' in script
    assert '!next.startsWith("//")' in script


class FakeDatabase:
    def __init__(self, fetchone_values=None, fetchall_value=None):
        self.fetchone_values = list(fetchone_values or [])
        self.fetchall_value = fetchall_value or []
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self):
        return self

    def execute(self, query, params=()):
        self.executed.append((query, params))

    def fetchone(self):
        return (
            self.fetchone_values.pop(0)
            if self.fetchone_values
            else None
        )

    def fetchall(self):
        return self.fetchall_value


def test_booking_cancellation_requires_authentication():
    response = client.post("/bookings/1/cancel")
    assert response.status_code == 401


def test_venue_hire_history_requires_authentication():
    response = client.get("/venue-hire/my-requests")
    assert response.status_code == 401


def test_notification_read_requires_authentication():
    response = client.patch("/notifications/1/read")
    assert response.status_code == 401


def test_individual_ticket_requires_authentication():
    response = client.get("/tickets/1")
    assert response.status_code == 401


def test_booking_cancellation_refunds_and_cancels_valid_tickets(monkeypatch):
    database = FakeDatabase(
        fetchone_values=[
            {"id": 10, "user_id": 7, "status": "CONFIRMED"},
            {"id": 20, "status": "SUCCESS"}
        ]
    )
    monkeypatch.setattr(
        bookings_module,
        "get_db_connection",
        lambda: database
    )
    monkeypatch.setattr(
        bookings_module,
        "_send_cancellation_notification",
        lambda request, user_id, booking_id: "SENT"
    )

    response = bookings_module.cancel_booking(
        10,
        SimpleNamespace(),
        {"id": 7, "role": "ATTENDEE"}
    )

    assert response["booking_status"] == "CANCELLED"
    assert response["payment_status"] == "REFUNDED"
    assert any("UPDATE payments" in query for query, _ in database.executed)
    assert any("UPDATE tickets" in query for query, _ in database.executed)


def test_booking_cancellation_rejects_already_cancelled(monkeypatch):
    database = FakeDatabase(
        fetchone_values=[
            {"id": 10, "user_id": 7, "status": "CANCELLED"}
        ]
    )
    monkeypatch.setattr(
        bookings_module,
        "get_db_connection",
        lambda: database
    )

    with pytest.raises(Exception) as error:
        bookings_module.cancel_booking(
            10,
            SimpleNamespace(),
            {"id": 7, "role": "ATTENDEE"}
        )

    assert error.value.status_code == 409


def test_venue_hire_history_uses_authenticated_user(monkeypatch):
    database = FakeDatabase(
        fetchall_value=[{"request_id": 3, "venue_name": "Hall"}]
    )
    monkeypatch.setattr(
        venue_hire_module,
        "get_db_connection",
        lambda: database
    )

    response = venue_hire_module.get_my_venue_hire_requests({"id": 12})

    assert response["requests"][0]["request_id"] == 3
    assert database.executed[0][1] == (12,)


def test_notification_read_updates_only_requested_owner(monkeypatch):
    database = FakeDatabase(
        fetchone_values=[{"id": 5, "is_read": True}]
    )
    monkeypatch.setattr(
        notifications_module,
        "get_db_connection",
        lambda: database
    )

    response = notifications_module.mark_notification_read(
        5,
        {"id": 12}
    )

    assert response["is_read"] is True
    assert database.executed[0][1] == (5, 12)


def test_ticket_details_query_is_owner_scoped(monkeypatch):
    database = FakeDatabase(
        fetchone_values=[{"ticket_id": 9, "ticket_status": "VALID"}]
    )
    monkeypatch.setattr(
        ticket_module,
        "get_db_connection",
        lambda: database
    )

    response = ticket_module.get_ticket_details(
        9,
        {"id": 12, "role": "ATTENDEE"}
    )

    assert response["ticket_id"] == 9
    assert database.executed[0][1] == (9, 12, "ATTENDEE")
