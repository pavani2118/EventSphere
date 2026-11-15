from fastapi.testclient import TestClient
from types import SimpleNamespace

import pytest

from app.main import app
import app.bookings as bookings_module
import app.notifications as notifications_module
import app.ticket as ticket_module
import app.venue_hire as venue_hire_module


client = TestClient(app)


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
