
import io
import qrcode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.database import get_db_connection
from app.dependencies import require_roles
from app.ticket_schemas import CheckInRequest
from app.agents.message import ACLMessage, Performative


router = APIRouter(
    prefix="/tickets",
    tags=["Ticket Management"]
)


# -------------------------------------------------
# 1. GET MY TICKETS
# -------------------------------------------------

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


# -------------------------------------------------
# 2. GENERATE TICKET QR CODE
# -------------------------------------------------

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


@router.get("/{ticket_id}")
def get_ticket_details(
    ticket_id: int,
    current_user=Depends(require_roles("ATTENDEE", "ADMIN", "GATE_STAFF"))
):
    if ticket_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid ticket ID.")

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.id AS ticket_id,
                       t.status AS ticket_status,
                       t.checked_in_at,
                       e.id AS event_id,
                       e.title AS event_title,
                       e.start_time,
                       e.end_time,
                       v.name AS venue_name,
                       tc.category_name,
                       b.id AS booking_id,
                       b.user_id
                FROM tickets t
                JOIN bookings b ON b.id = t.booking_id
                JOIN events e ON e.id = b.event_id
                JOIN venues v ON v.id = e.venue_id
                JOIN ticket_categories tc ON tc.id = t.category_id
                WHERE t.id = %s
                  AND (
                      b.user_id = %s
                      OR %s IN ('ADMIN', 'GATE_STAFF')
                  )
                """,
                (ticket_id, current_user["id"], current_user["role"])
            )
            ticket = cursor.fetchone()

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    return ticket


# -------------------------------------------------
# 3. CHECK-IN THROUGH TICKET AGENT
# -------------------------------------------------

@router.post("/check-in")
def check_in_ticket(
    data: CheckInRequest,
    request: Request,
    current_user=Depends(
        require_roles("GATE_STAFF", "ADMIN")
    )
):

    # Get agent runtime.
    runtime = request.app.state.agent_runtime

    message_bus = runtime["message_bus"]

    # Validate and clean QR token.
    qr_token = data.qr_token.strip()

    # Create ACL REQUEST.
    checkin_request = ACLMessage(
        sender="TicketAPI",
        receiver="TicketAgent",
        performative=Performative.REQUEST,
        content={
            "action": "CHECK_IN",
            "qr_token": qr_token,
            "staff_user_id": current_user["id"]
        }
    )

    # Send request to TicketAgent.
    response = message_bus.send(checkin_request)

    # ---------------------------------------------
    # HANDLE REFUSAL
    # ---------------------------------------------

    if response.performative == Performative.REFUSE:

        reason = response.content.get(
            "reason",
            "Ticket check-in was rejected."
        )

        reason_lower = reason.lower()

        if (
            "not found" in reason_lower
            or "invalid qr" in reason_lower
        ):
            status_code = 404

        elif (
            "already" in reason_lower
            or "used" in reason_lower
        ):
            status_code = 409

        else:
            status_code = 400

        raise HTTPException(
            status_code=status_code,
            detail=reason
        )

    # ---------------------------------------------
    # HANDLE UNEXPECTED RESPONSE
    # ---------------------------------------------

    if response.performative != Performative.AGREE:

        raise HTTPException(
            status_code=500,
            detail=response.content.get(
                "reason",
                "TicketAgent could not complete check-in."
            )
        )

    # ---------------------------------------------
    # SUCCESS RESPONSE
    # ---------------------------------------------

    return {
        "message": "Check-in successful",
        **response.content
    }
