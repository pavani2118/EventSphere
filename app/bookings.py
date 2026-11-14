
from fastapi import APIRouter, Depends, HTTPException, Request

from app.database import get_db_connection
from app.dependencies import require_roles
from app.booking_schemas import BookingCreate

from app.agents.message import ACLMessage, Performative


router = APIRouter(
    prefix="/bookings",
    tags=["Booking Management"]
)


# --------------------------------------------------
# CREATE BOOKING THROUGH BOOKING AGENT
# --------------------------------------------------

@router.post("/", status_code=201)
def create_booking(
    data: BookingCreate,
    request: Request,
    current_user=Depends(require_roles("ATTENDEE"))
):

    # Get the running agent system
    runtime = request.app.state.agent_runtime
    message_bus = runtime["message_bus"]

    # Create ACL REQUEST message
    booking_request = ACLMessage(
        sender="BookingAPI",
        receiver="BookingAgent",
        performative=Performative.REQUEST,
        content={
            "action": "CREATE_BOOKING",
            "user_id": current_user["id"],
            "event_id": data.event_id,
            "category_id": data.category_id,
            "quantity": data.quantity
        }
    )

    # Send request to BookingAgent
    response = message_bus.send(booking_request)

    # Handle agent response
    if response.performative == Performative.REFUSE:
        raise HTTPException(
            status_code=400,
            detail=response.content.get(
                "reason",
                "Booking request was rejected."
            )
        )

    if response.performative != Performative.AGREE:
        raise HTTPException(
            status_code=500,
            detail=response.content.get(
                "reason",
                "Booking agent could not complete the request."
            )
        )

    return response.content


# --------------------------------------------------
# VIEW MY BOOKING HISTORY
# --------------------------------------------------

@router.get("/my-bookings")
def get_my_bookings(
    current_user=Depends(require_roles("ATTENDEE"))
):

    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    b.id AS booking_id,
                    b.event_id,
                    e.title AS event_title,
                    b.quantity,
                    b.total_amount,
                    b.status AS booking_status,
                    b.created_at,
                    p.payment_reference,
                    p.status AS payment_status
                FROM bookings b
                JOIN events e ON e.id = b.event_id
                LEFT JOIN payments p ON p.booking_id = b.id
                WHERE b.user_id = %s
                ORDER BY b.created_at DESC
                """,
                (current_user["id"],)
            )

            bookings = cursor.fetchall()

    return {
        "total_bookings": len(bookings),
        "bookings": bookings
    }
