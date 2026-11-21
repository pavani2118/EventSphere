
from fastapi import APIRouter, Depends, HTTPException, Request

from app.database import get_db_connection
from app.dependencies import require_roles
from app.booking_schemas import BookingCreate, PaymentSimulationRequest

from app.agents.message import ACLMessage, Performative


router = APIRouter(
    prefix="/bookings",
    tags=["Booking Management"]
)


def _send_cancellation_notification(request, user_id, booking_id):
    runtime = getattr(request.app.state, "agent_runtime", None)
    if runtime is None:
        return "UNAVAILABLE"

    message = ACLMessage(
        sender="BookingAPI",
        receiver="NotificationAgent",
        performative=Performative.INFORM,
        content={
            "action": "SEND_NOTIFICATION",
            "user_id": user_id,
            "message": (
                f"Booking #{booking_id} was cancelled and the payment "
                "was refunded."
            )
        }
    )

    try:
        response = runtime["message_bus"].send(message)
    except Exception:
        return "FAILED"

    return (
        "SENT"
        if response and response.performative == Performative.AGREE
        else "FAILED"
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
            "quantity": data.quantity,
            "payment_result": data.payment_result
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


@router.post("/{booking_id}/payment")
def process_simulated_payment(
    booking_id: int,
    data: PaymentSimulationRequest,
    request: Request,
    current_user=Depends(require_roles("ATTENDEE"))
):
    if booking_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid booking ID.")

    runtime = getattr(request.app.state, "agent_runtime", None)
    if runtime is None:
        raise HTTPException(
            status_code=503,
            detail="Agent system is not available."
        )

    message = ACLMessage(
        sender="BookingAPI",
        receiver="BookingAgent",
        performative=Performative.REQUEST,
        content={
            "action": "PROCESS_PAYMENT",
            "booking_id": booking_id,
            "user_id": current_user["id"],
            "category_id": data.category_id,
            "payment_result": data.payment_result
        }
    )
    response = runtime["message_bus"].send(message)

    if response.performative == Performative.REFUSE:
        raise HTTPException(
            status_code=400,
            detail=response.content.get(
                "reason",
                "Payment could not be processed."
            )
        )
    if response.performative != Performative.AGREE:
        raise HTTPException(
            status_code=500,
            detail=response.content.get(
                "reason",
                "Payment agent could not complete the request."
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


@router.post("/{booking_id}/cancel")
def cancel_booking(
    booking_id: int,
    request: Request,
    current_user=Depends(require_roles("ATTENDEE", "ADMIN"))
):
    if booking_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid booking ID.")

    is_admin = current_user["role"] == "ADMIN"

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, status
                FROM bookings
                WHERE id = %s
                FOR UPDATE
                """,
                (booking_id,)
            )
            booking = cursor.fetchone()

            if booking is None:
                raise HTTPException(
                    status_code=404,
                    detail="Booking not found."
                )

            if not is_admin and booking["user_id"] != current_user["id"]:
                raise HTTPException(
                    status_code=403,
                    detail="You can only cancel your own bookings."
                )

            if booking["status"] == "CANCELLED":
                raise HTTPException(
                    status_code=409,
                    detail="Booking is already cancelled."
                )

            if booking["status"] != "CONFIRMED":
                raise HTTPException(
                    status_code=400,
                    detail="Only confirmed bookings can be cancelled."
                )

            cursor.execute(
                """
                SELECT id, status
                FROM payments
                WHERE booking_id = %s
                ORDER BY id DESC
                LIMIT 1
                FOR UPDATE
                """,
                (booking_id,)
            )
            payment = cursor.fetchone()

            if payment and payment["status"] == "SUCCESS":
                cursor.execute(
                    """
                    UPDATE payments
                    SET status = 'REFUNDED'
                    WHERE id = %s
                      AND status = 'SUCCESS'
                    """,
                    (payment["id"],)
                )
            elif payment and payment["status"] == "REFUNDED":
                raise HTTPException(
                    status_code=409,
                    detail="Payment has already been refunded."
                )

            cursor.execute(
                """
                UPDATE tickets
                SET status = 'CANCELLED'
                WHERE booking_id = %s
                  AND status = 'VALID'
                """,
                (booking_id,)
            )

            cursor.execute(
                """
                UPDATE bookings
                SET status = 'CANCELLED'
                WHERE id = %s
                  AND status = 'CONFIRMED'
                """,
                (booking_id,)
            )

    notification_status = _send_cancellation_notification(
        request,
        booking["user_id"],
        booking_id
    )

    return {
        "success": True,
        "booking_id": booking_id,
        "booking_status": "CANCELLED",
        "payment_status": (
            "REFUNDED" if payment and payment["status"] == "SUCCESS"
            else payment["status"] if payment else "NOT_FOUND"
        ),
        "notification_status": notification_status
    }
