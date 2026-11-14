import io
import qrcode

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.database import get_db_connection
from app.dependencies import require_roles
from app.ticket_schemas import CheckInRequest


router = APIRouter(
    prefix="/tickets",
    tags=["Ticket Management"]
)


# 1. Get tickets belonging to the logged-in attendee
@router.get("/my-tickets")
def get_my_tickets(
    current_user=Depends(require_roles("ATTENDEE"))
):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    t.id AS ticket_id,
                    t.qr_token,
                    t.status AS ticket_status,
                    e.title AS event_title,
                    e.start_time,
                    e.end_time,
                    v.name AS venue_name,
                    tc.category_name,
                    b.id AS booking_id

                FROM tickets t

                JOIN bookings b
                    ON t.booking_id = b.id

                JOIN events e
                    ON b.event_id = e.id

                JOIN venues v
                    ON e.venue_id = v.id

                JOIN ticket_categories tc
                    ON t.category_id = tc.id

                WHERE b.user_id = %s

                ORDER BY t.id DESC
                """,
                (current_user["id"],)
            )

            tickets = cursor.fetchall()

    return {
        "total_tickets": len(tickets),
        "tickets": tickets
    }


# 2. Generate QR code image for an attendee's ticket
@router.get("/{ticket_id}/qr")
def generate_ticket_qr(
    ticket_id: int,
    current_user=Depends(require_roles("ATTENDEE"))
):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT t.qr_token
                FROM tickets t

                JOIN bookings b
                    ON t.booking_id = b.id

                WHERE t.id = %s
                  AND b.user_id = %s
                """,
                (ticket_id, current_user["id"])
            )

            ticket = cursor.fetchone()

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    qr = qrcode.make(ticket["qr_token"])

    image_buffer = io.BytesIO()
    qr.save(image_buffer, format="PNG")
    image_buffer.seek(0)

    return StreamingResponse(
        image_buffer,
        media_type="image/png",
        headers={
            "Content-Disposition":
                f"inline; filename=ticket_{ticket_id}.png"
        }
    )


# 3. Validate QR token and check in attendee
@router.post("/check-in")
def check_in_ticket(
    data: CheckInRequest,
    current_user=Depends(
        require_roles("GATE_STAFF", "ADMIN")
    )
):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            # Lock ticket row to prevent double check-in
            cursor.execute(
                """
                SELECT
                    t.id,
                    t.status,
                    t.qr_token,
                    e.status AS event_status,
                    e.title AS event_title,
                    tc.category_name

                FROM tickets t

                JOIN bookings b
                    ON t.booking_id = b.id

                JOIN events e
                    ON b.event_id = e.id

                JOIN ticket_categories tc
                    ON t.category_id = tc.id

                WHERE t.qr_token = %s

                FOR UPDATE OF t
                """,
                (data.qr_token,)
            )

            ticket = cursor.fetchone()

            if ticket is None:
                raise HTTPException(
                    status_code=404,
                    detail="Invalid QR code. Ticket not found."
                )

            if ticket["status"] == "USED":
                raise HTTPException(
                    status_code=409,
                    detail="Ticket has already been used."
                )

            if ticket["status"] == "CANCELLED":
                raise HTTPException(
                    status_code=400,
                    detail="This ticket has been cancelled."
                )

            if ticket["status"] != "VALID":
                raise HTTPException(
                    status_code=400,
                    detail="Ticket is not valid."
                )

            if ticket["event_status"] == "CANCELLED":
                raise HTTPException(
                    status_code=400,
                    detail="This event has been cancelled."
                )

            cursor.execute(
                """
                UPDATE tickets

                SET
                    status = 'USED',
                    checked_in_at = NOW(),
                    checked_in_by = %s

                WHERE id = %s
                  AND status = 'VALID'

                RETURNING id, status, checked_in_at
                """,
                (current_user["id"], ticket["id"])
            )

            checked_ticket = cursor.fetchone()

            if checked_ticket is None:
                raise HTTPException(
                    status_code=409,
                    detail="Ticket has already been checked in."
                )

    return {
        "message": "Check-in successful",
        "ticket_id": checked_ticket["id"],
        "event_title": ticket["event_title"],
        "category": ticket["category_name"],
        "ticket_status": checked_ticket["status"],
        "checked_in_at": checked_ticket["checked_in_at"]
    }