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
import app.gate_staff as gate_staff_module
import app.waitlist as waitlist_module
import app.notifications as notifications_module
import app.dashboard as dashboard_module
import app.events as events_module
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


def test_gate_validation_accepts_valid_successful_ticket():
    ticket = {
        "ticket_id": 7,
        "ticket_status": "VALID",
        "booking_status": "CONFIRMED",
        "payment_status": "SUCCESS",
        "event_status": "PUBLISHED",
    }

    status_code, message = gate_staff_module.validation_status(ticket)

    assert status_code == "VALID"
    assert "valid" in message.lower()


def test_gate_validation_rejects_incomplete_payment():
    ticket = {
        "ticket_id": 7,
        "ticket_status": "VALID",
        "booking_status": "CONFIRMED",
        "payment_status": "PENDING",
        "event_status": "PUBLISHED",
    }

    status_code, message = gate_staff_module.validation_status(ticket)

    assert status_code == "PAYMENT_NOT_COMPLETED"
    assert "payment" in message.lower()


def test_gate_validation_rejects_used_ticket():
    ticket = {
        "ticket_id": 7,
        "ticket_status": "USED",
        "booking_status": "CONFIRMED",
        "payment_status": "SUCCESS",
        "event_status": "PUBLISHED",
    }

    status_code, message = gate_staff_module.validation_status(ticket)

    assert status_code == "ALREADY_CHECKED_IN"


def test_gate_validation_rejects_cancelled_event():
    ticket = {
        "ticket_id": 7,
        "ticket_status": "VALID",
        "booking_status": "CONFIRMED",
        "payment_status": "SUCCESS",
        "event_status": "CANCELLED",
    }

    status_code, message = gate_staff_module.validation_status(ticket)

    assert status_code == "EVENT_NOT_VALID"


def test_gate_dashboard_requires_authentication():
    response = client.get("/gate/dashboard")
    assert response.status_code == 401


def test_gate_dashboard_rejects_attendee(monkeypatch):
    monkeypatch.setattr(
        dependencies_module,
        "get_user_from_token",
        lambda token: {"id": 184, "role": "ATTENDEE"}
    )
    response = client.get(
        "/gate/dashboard",
        headers={"Authorization": "Bearer valid-attendee-token"}
    )
    assert response.status_code == 403


def test_gate_dashboard_allows_gate_staff(monkeypatch):
    monkeypatch.setattr(
        dependencies_module,
        "get_user_from_token",
        lambda token: {"id": 25, "role": "GATE_STAFF"}
    )

    database = FakeDatabase(fetchall_value=[], fetchone_values=[{
        "total_issued_today": 0,
        "checked_in_today": 0,
        "remaining_today": 0
    }])
    monkeypatch.setattr(
        gate_staff_module,
        "get_db_connection",
        lambda: database
    )

    response = client.get(
        "/gate/dashboard",
        headers={"Authorization": "Bearer valid-gate-token"}
    )
    assert response.status_code == 200


def test_gate_dashboard_allows_admin(monkeypatch):
    monkeypatch.setattr(
        dependencies_module,
        "get_user_from_token",
        lambda token: {"id": 1, "role": "ADMIN"}
    )

    database = FakeDatabase(fetchall_value=[], fetchone_values=[{
        "total_issued_today": 0,
        "checked_in_today": 0,
        "remaining_today": 0
    }])
    monkeypatch.setattr(
        gate_staff_module,
        "get_db_connection",
        lambda: database
    )

    response = client.get(
        "/gate/dashboard",
        headers={"Authorization": "Bearer valid-admin-token"}
    )
    assert response.status_code == 200


def test_gate_validate_requires_authentication():
    response = client.post(
        "/gate/tickets/validate",
        json={"qr_token": "A" * 32}
    )
    assert response.status_code == 401


def test_gate_history_requires_authentication():
    response = client.get("/gate/check-ins")
    assert response.status_code == 401


def test_gate_check_in_route_accepts_valid_gate_staff(monkeypatch):
    class SuccessfulCheckInBus:
        def send(self, message):
            return ACLMessage(
                sender="TicketAgent",
                receiver="GateAPI",
                performative=Performative.AGREE,
                conversation_id=message.conversation_id,
                content={
                    "success": True,
                    "ticket_id": 9,
                    "event_id": 3,
                    "event_title": "Test Event",
                    "attendee_name": "Test Attendee",
                    "checked_in_at": "2026-11-21T12:00:00+00:00"
                }
            )

    monkeypatch.setattr(
        dependencies_module,
        "get_user_from_token",
        lambda token: {"id": 25, "role": "GATE_STAFF"}
    )

    with client:
        app.state.agent_runtime = {"message_bus": SuccessfulCheckInBus()}
        response = client.post(
            "/gate/tickets/check-in",
            headers={"Authorization": "Bearer valid-gate-token"},
            json={"qr_token": "A" * 32}
        )

    assert response.status_code == 200
    assert response.json()["ticket_id"] == 9
    assert response.json()["result"] == "VALID"


def test_gate_check_in_route_rejects_attendee(monkeypatch):
    monkeypatch.setattr(
        dependencies_module,
        "get_user_from_token",
        lambda token: {"id": 184, "role": "ATTENDEE"}
    )
    response = client.post(
        "/gate/tickets/check-in",
        headers={"Authorization": "Bearer valid-attendee-token"},
        json={"qr_token": "A" * 32}
    )
    assert response.status_code == 403


def test_gate_history_retrieval_filters_records(monkeypatch):
    monkeypatch.setattr(
        dependencies_module,
        "get_user_from_token",
        lambda token: {"id": 25, "role": "GATE_STAFF"}
    )

    database = FakeDatabase(
        fetchone_values=[{"count": 1}],
        fetchall_value=[{
            "ticket_id": 9,
            "event_title": "Test Event",
            "attendee_name": "Test Attendee",
            "staff_name": "Gate Staff",
            "checked_in_at": "2026-11-21T12:00:00+00:00"
        }]
    )
    monkeypatch.setattr(
        gate_staff_module,
        "get_db_connection",
        lambda: database
    )

    response = client.get(
        "/gate/check-ins?ticket_id=9",
        headers={"Authorization": "Bearer valid-gate-token"}
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["check_ins"][0]["ticket_id"] == 9


def test_waitlist_owner_can_leave_waitlist(monkeypatch):
    database = FakeDatabase(fetchone_values=[{"id": 12}])
    monkeypatch.setattr(
        waitlist_module,
        "get_db_connection",
        lambda: database
    )

    response = waitlist_module.cancel_waitlist_entry(
        12,
        {"id": 184, "role": "ATTENDEE"}
    )

    assert response["status"] == "CANCELLED"
    assert "UPDATE waitlist" in database.executed[0][0]
    assert database.executed[0][1] == (12, 184)


def test_waitlist_leave_rejects_missing_owned_entry(monkeypatch):
    database = FakeDatabase(fetchone_values=[None])
    monkeypatch.setattr(
        waitlist_module,
        "get_db_connection",
        lambda: database
    )

    with pytest.raises(HTTPException) as error:
        waitlist_module.cancel_waitlist_entry(
            12,
            {"id": 184, "role": "ATTENDEE"}
        )

    assert error.value.status_code == 404


def test_mark_all_notifications_updates_owner_records(monkeypatch):
    database = FakeDatabase(fetchall_value=[{"id": 1}, {"id": 2}])
    monkeypatch.setattr(
        notifications_module,
        "get_db_connection",
        lambda: database
    )

    response = notifications_module.mark_all_notifications_read(
        {"id": 184}
    )

    assert response["updated_count"] == 2
    assert "AND is_read = FALSE" in database.executed[0][0]
    assert database.executed[0][1] == (184,)


def test_organiser_summary_uses_organiser_id(monkeypatch):
    database = FakeDatabase(
        fetchone_values=[
            {
                "total_events": 3,
                "published_events": 2,
                "draft_events": 1,
                "cancelled_events": 0
            },
            {
                "total_bookings": 5,
                "confirmed_bookings": 4,
                "total_tickets": 8,
                "active_tickets": 7
            },
            {"total_revenue": 50000},
        ],
        fetchall_value=[{
            "booking_id": 9,
            "event_title": "Test Event"
        }]
    )
    monkeypatch.setattr(
        dashboard_module,
        "get_db_connection",
        lambda: database
    )

    response = dashboard_module.get_organiser_summary(
        {"id": 25, "role": "ORGANISER"}
    )

    assert response["total_events"] == 3
    assert response["total_revenue"] == 50000
    assert all(
        call_params == (25,)
        for _, call_params in database.executed
    )


def test_organiser_rejects_admin_summary():
    with pytest.raises(HTTPException) as error:
        dashboard_module.get_organiser_summary(
            {"id": 1, "role": "ADMIN"}
        )
    assert error.value.status_code == 403


def test_organiser_bookings_are_owner_scoped(monkeypatch):
    database = FakeDatabase(fetchall_value=[
        {"booking_id": 9, "event_id": 3}
    ])
    monkeypatch.setattr(
        dashboard_module,
        "get_db_connection",
        lambda: database
    )

    response = dashboard_module.get_organiser_bookings(
        event_id=3,
        status="CONFIRMED",
        current_user={"id": 25, "role": "ORGANISER"}
    )

    assert response["total"] == 1
    query, params = database.executed[0]
    assert "e.created_by = %s" in query
    assert params == (25, 3, "CONFIRMED")


def test_unpublish_rejects_event_with_existing_bookings(monkeypatch):
    database = FakeDatabase(
        fetchone_values=[
            {"id": 3, "status": "PUBLISHED", "created_by": 25},
            {"booking_count": 2}
        ]
    )
    monkeypatch.setattr(
        events_module,
        "get_db_connection",
        lambda: database
    )

    with pytest.raises(HTTPException) as error:
        events_module.unpublish_event(
            3,
            {"id": 25, "role": "ORGANISER"}
        )

    assert error.value.status_code == 409


def test_failed_simulated_payment_creates_no_success_tickets():
    with open(
        "app/agents/booking_agent.py",
        "r",
        encoding="utf-8"
    ) as source_file:
        source = source_file.read()

    assert 'payment_result not in {"SUCCESS", "FAILED"}' in source
    assert 'payment_result == "SUCCESS"' in source
    assert 'payment_status = payment_result' in source or (
        '"payment_status": payment_result' in source
    )


def test_successful_simulated_payment_route(monkeypatch):
    class PaymentBus:
        def send(self, message):
            assert message.content["action"] == "PROCESS_PAYMENT"
            return ACLMessage(
                sender="BookingAgent",
                receiver="BookingAPI",
                performative=Performative.AGREE,
                conversation_id=message.conversation_id,
                content={
                    "booking_id": 42,
                    "booking_status": "CONFIRMED",
                    "payment_status": "SUCCESS",
                    "tickets": [{"ticket_id": 1}]
                }
            )

    monkeypatch.setattr(
        dependencies_module,
        "get_user_from_token",
        lambda token: {"id": 184, "role": "ATTENDEE"}
    )

    with client:
        app.state.agent_runtime = {"message_bus": PaymentBus()}
        response = client.post(
            "/bookings/42/payment",
            headers={"Authorization": "Bearer valid-attendee-token"},
            json={
                "payment_result": "SUCCESS",
                "category_id": 2
            }
        )

    assert response.status_code == 200
    assert response.json()["payment_status"] == "SUCCESS"


def test_failed_simulated_payment_route(monkeypatch):
    class PaymentBus:
        def send(self, message):
            return ACLMessage(
                sender="BookingAgent",
                receiver="BookingAPI",
                performative=Performative.AGREE,
                conversation_id=message.conversation_id,
                content={
                    "booking_id": 42,
                    "booking_status": "PENDING",
                    "payment_status": "FAILED",
                    "tickets": []
                }
            )

    monkeypatch.setattr(
        dependencies_module,
        "get_user_from_token",
        lambda token: {"id": 184, "role": "ATTENDEE"}
    )

    with client:
        app.state.agent_runtime = {"message_bus": PaymentBus()}
        response = client.post(
            "/bookings/42/payment",
            headers={"Authorization": "Bearer valid-attendee-token"},
            json={
                "payment_result": "FAILED",
                "category_id": 2
            }
        )

    assert response.status_code == 200
    assert response.json()["payment_status"] == "FAILED"
    assert response.json()["tickets"] == []


def test_organiser_dashboard_page_route():
    response = client.get("/ui/organiser/dashboard")
    assert response.status_code == 200
    assert b"Organiser Dashboard" in response.content


def test_organiser_dashboard_frontend_uses_real_api():
    with open(
        "app/static/js/organiser-dashboard.js",
        "r",
        encoding="utf-8"
    ) as script_file:
        script = script_file.read()

    assert "/dashboard/organiser/summary" in script
    assert "/dashboard/organiser/bookings" in script


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
