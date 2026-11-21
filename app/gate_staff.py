from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from app.agents.message import ACLMessage, Performative

from app.database import get_db_connection
from app.dependencies import require_roles


router = APIRouter(prefix="/gate", tags=["Gate Staff"])


class QRValidationRequest(BaseModel):
    qr_token: str = Field(min_length=1, max_length=200)


class GateCheckInRequest(BaseModel):
    qr_token: str | None = Field(default=None, max_length=200)
    ticket_id: int | None = Field(default=None, gt=0)


def require_gate_user(current_user):
    role = current_user["role"]
    if role not in {"GATE_STAFF", "ADMIN"}:
        raise HTTPException(
            status_code=403,
            detail="Gate Staff or Admin access required"
        )
    return current_user


def get_gate_ticket(qr_token: str):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    t.id AS ticket_id,
                    t.status AS ticket_status,
                    t.checked_in_at,
                    t.checked_in_by,
                    t.qr_token,
                    b.id AS booking_id,
                    b.status AS booking_status,
                    b.quantity,
                    u.id AS attendee_id,
                    u.full_name AS attendee_name,
                    u.email AS attendee_email,
                    e.id AS event_id,
                    e.title AS event_title,
                    e.status AS event_status,
                    e.start_time,
                    e.end_time,
                    v.name AS venue_name,
                    tc.category_name,
                    p.status AS payment_status,
                    p.amount AS payment_amount,
                    p.payment_reference
                FROM tickets t
                JOIN bookings b ON b.id = t.booking_id
                JOIN users u ON u.id = b.user_id
                JOIN events e ON e.id = b.event_id
                JOIN venues v ON v.id = e.venue_id
                JOIN ticket_categories tc ON tc.id = t.category_id
                LEFT JOIN LATERAL (
                    SELECT p.status, p.amount, p.payment_reference
                    FROM payments p
                    WHERE p.booking_id = b.id
                    ORDER BY p.id DESC
                    LIMIT 1
                ) p ON TRUE
                WHERE t.qr_token = %s
                """,
                (qr_token,)
            )
            return cursor.fetchone()


def validation_status(ticket):
    if ticket is None:
        return "NOT_FOUND", "Ticket not found."
    if ticket["ticket_status"] == "CANCELLED":
        return "INVALID_TICKET", "This ticket has been cancelled."
    if ticket["ticket_status"] == "USED":
        return "ALREADY_CHECKED_IN", "Ticket has already been checked in."
    if ticket["ticket_status"] != "VALID":
        return "INVALID_TICKET", "Ticket is not valid."
    if ticket["payment_status"] != "SUCCESS":
        return "PAYMENT_NOT_COMPLETED", "Payment has not completed successfully."
    if ticket["booking_status"] != "CONFIRMED":
        return "INVALID_TICKET", "The booking is not confirmed."
    if ticket["event_status"] != "PUBLISHED":
        return "EVENT_NOT_VALID", "This event is not published and valid for check-in."
    return "VALID", "Ticket is valid."


@router.get("/dashboard")
def gate_dashboard(
    current_user=Depends(require_roles("GATE_STAFF", "ADMIN")),
    event_id: int | None = None,
):
    require_gate_user(current_user)

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    e.id AS event_id,
                    e.title,
                    e.category,
                    e.start_time,
                    e.end_time,
                    e.status,
                    v.name AS venue_name,
                    v.location AS venue_location,
                    COUNT(t.id) AS total_issued,
                    COUNT(t.id) FILTER (WHERE t.status = 'USED') AS checked_in,
                    COUNT(t.id) FILTER (
                        WHERE t.status = 'VALID'
                    ) AS remaining
                FROM events e
                JOIN venues v ON v.id = e.venue_id
                LEFT JOIN bookings b ON b.event_id = e.id
                LEFT JOIN tickets t ON t.booking_id = b.id
                WHERE e.status = 'PUBLISHED'
                  AND (%s::BIGINT IS NULL OR e.id = %s)
                GROUP BY
                    e.id, e.title, e.category, e.start_time, e.end_time,
                    e.status, v.name, v.location
                ORDER BY e.start_time ASC
                """,
                (event_id, event_id),
            )
            events = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    t.id AS ticket_id,
                    t.checked_in_at,
                    e.id AS event_id,
                    e.title AS event_title,
                    u.full_name AS attendee_name,
                    staff.full_name AS staff_name
                FROM tickets t
                JOIN bookings b ON b.id = t.booking_id
                JOIN users u ON u.id = b.user_id
                JOIN events e ON e.id = b.event_id
                LEFT JOIN users staff ON staff.id = t.checked_in_by
                WHERE t.status = 'USED'
                  AND t.checked_in_at IS NOT NULL
                  AND (%s::BIGINT IS NULL OR e.id = %s)
                ORDER BY t.checked_in_at DESC
                LIMIT 10
                """,
                (event_id, event_id),
            )
            recent_check_ins = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    COUNT(t.id) AS total_issued_today,
                    COUNT(t.id) FILTER (WHERE t.status = 'USED') AS checked_in_today,
                    COUNT(t.id) FILTER (WHERE t.status = 'VALID') AS remaining_today
                FROM events e
                JOIN bookings b ON b.event_id = e.id
                JOIN tickets t ON t.booking_id = b.id
                WHERE e.status = 'PUBLISHED'
                  AND e.start_time::DATE = CURRENT_DATE
                  AND (%s::BIGINT IS NULL OR e.id = %s)
                """,
                (event_id, event_id),
            )
            today_stats = cursor.fetchone()

    today = date.today()
    selected = events[0] if event_id is not None and events else (events[0] if events else None)

    return {
        "date": today.isoformat(),
        "total_tickets_expected_today": int(today_stats["total_issued_today"] or 0),
        "total_checked_in_today": int(today_stats["checked_in_today"] or 0),
        "remaining_tickets": int(today_stats["remaining_today"] or 0),
        "selected_event": selected,
        "events": events,
        "recent_check_ins": recent_check_ins,
    }


@router.get("/events")
def gate_events(
    current_user=Depends(require_roles("GATE_STAFF", "ADMIN")),
):
    require_gate_user(current_user)
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    e.id AS event_id,
                    e.title,
                    e.category,
                    e.start_time,
                    e.end_time,
                    e.status,
                    v.name AS venue_name,
                    v.location AS venue_location,
                    COUNT(t.id) AS total_issued,
                    COUNT(t.id) FILTER (WHERE t.status = 'USED') AS checked_in,
                    COUNT(t.id) FILTER (WHERE t.status = 'VALID') AS remaining
                FROM events e
                JOIN venues v ON v.id = e.venue_id
                LEFT JOIN bookings b ON b.event_id = e.id
                LEFT JOIN tickets t ON t.booking_id = b.id
                WHERE e.status = 'PUBLISHED'
                GROUP BY
                    e.id, e.title, e.category, e.start_time, e.end_time,
                    e.status, v.name, v.location
                ORDER BY e.start_time ASC
                """
            )
            events = cursor.fetchall()
    return {"total": len(events), "events": events}


@router.post("/tickets/validate")
def validate_gate_ticket(
    data: QRValidationRequest,
    current_user=Depends(require_roles("GATE_STAFF", "ADMIN")),
):
    require_gate_user(current_user)
    value = data.qr_token.strip()
    ticket = None

    if value.isdigit():
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT qr_token FROM tickets WHERE id = %s",
                    (int(value),),
                )
                ticket_row = cursor.fetchone()
        ticket = get_gate_ticket(ticket_row["qr_token"]) if ticket_row else None
    else:
        ticket = get_gate_ticket(value)
    status_code, message = validation_status(ticket)

    if ticket is None:
        return {
            "result": status_code,
            "valid": False,
            "message": message,
        }

    return {
        "result": status_code,
        "valid": status_code == "VALID",
        "message": message,
        "ticket_id": ticket["ticket_id"],
        "event_id": ticket["event_id"],
        "event_title": ticket["event_title"],
        "event_status": ticket["event_status"],
        "venue_name": ticket["venue_name"],
        "attendee_name": ticket["attendee_name"],
        "category": ticket["category_name"],
        "ticket_status": ticket["ticket_status"],
        "booking_status": ticket["booking_status"],
        "payment_status": ticket["payment_status"],
        "checked_in_at": ticket["checked_in_at"],
    }


@router.post("/tickets/check-in")
def confirm_gate_check_in(
    data: GateCheckInRequest,
    request: Request,
    current_user=Depends(require_roles("GATE_STAFF", "ADMIN")),
):
    require_gate_user(current_user)

    qr_token = data.qr_token.strip() if data.qr_token else None

    if not qr_token and data.ticket_id:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT qr_token FROM tickets WHERE id = %s",
                    (data.ticket_id,),
                )
                ticket_row = cursor.fetchone()

        qr_token = ticket_row["qr_token"] if ticket_row else None

    if not qr_token:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found.",
        )

    runtime = request.app.state.agent_runtime
    message = ACLMessage(
        sender="GateAPI",
        receiver="TicketAgent",
        performative=Performative.REQUEST,
        content={
            "action": "CHECK_IN",
            "qr_token": qr_token,
            "staff_user_id": current_user["id"],
        },
    )
    response = runtime["message_bus"].send(message)

    if response.performative == Performative.REFUSE:
        reason = response.content.get(
            "reason",
            "Ticket check-in was rejected.",
        )
        reason_lower = reason.lower()
        if "already" in reason_lower or "used" in reason_lower:
            status_code = 409
        elif "not found" in reason_lower or "invalid qr" in reason_lower:
            status_code = 404
        elif "payment" in reason_lower:
            status_code = 402
        elif "event" in reason_lower:
            status_code = 400
        else:
            status_code = 400

        raise HTTPException(
            status_code=status_code,
            detail={
                "message": reason,
                "result": response.content.get("result", "INVALID_TICKET"),
            },
        )

    if response.performative != Performative.AGREE:
        raise HTTPException(
            status_code=500,
            detail="TicketAgent could not complete check-in.",
        )

    return {
        "message": "Check-in successful",
        "result": "VALID",
        **response.content,
    }


@router.get("/check-ins")
def get_gate_check_ins(
    current_user=Depends(require_roles("GATE_STAFF", "ADMIN")),
    ticket_id: int | None = Query(default=None, gt=0),
    attendee: str | None = None,
    event_id: int | None = Query(default=None, gt=0),
    checked_in_date: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    require_gate_user(current_user)
    offset = (page - 1) * page_size

    filters = ["t.status = 'USED'", "t.checked_in_at IS NOT NULL"]
    params = []

    if ticket_id is not None:
        filters.append("t.id = %s")
        params.append(ticket_id)
    if attendee:
        filters.append("(u.full_name ILIKE %s OR u.email ILIKE %s)")
        params.extend([f"%{attendee}%", f"%{attendee}%"])
    if event_id is not None:
        filters.append("e.id = %s")
        params.append(event_id)
    if checked_in_date is not None:
        filters.append("t.checked_in_at::DATE = %s")
        params.append(checked_in_date)

    where_clause = " AND ".join(filters)

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM tickets t
                JOIN bookings b ON b.id = t.booking_id
                JOIN users u ON u.id = b.user_id
                JOIN events e ON e.id = b.event_id
                WHERE {where_clause}
                """,
                tuple(params),
            )
            count = cursor.fetchone()

            cursor.execute(
                f"""
                SELECT
                    t.id AS ticket_id,
                    t.status AS ticket_status,
                    t.checked_in_at,
                    e.id AS event_id,
                    e.title AS event_title,
                    u.full_name AS attendee_name,
                    u.email AS attendee_email,
                    staff.full_name AS staff_name,
                    staff.id AS staff_id
                FROM tickets t
                JOIN bookings b ON b.id = t.booking_id
                JOIN users u ON u.id = b.user_id
                JOIN events e ON e.id = b.event_id
                LEFT JOIN users staff ON staff.id = t.checked_in_by
                WHERE {where_clause}
                ORDER BY t.checked_in_at DESC, t.id DESC
                LIMIT %s OFFSET %s
                """,
                tuple(params + [page_size, offset]),
            )
            rows = cursor.fetchall()

    total = int(count["count"]) if count else 0
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "check_ins": rows,
    }
