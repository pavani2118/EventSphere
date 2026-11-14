
import secrets

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db_connection
from app.dependencies import require_roles
from app.booking_schemas import BookingCreate


router = APIRouter(
    prefix="/bookings",
    tags=["Booking Management"]
)


# --------------------------------------------------
# CREATE BOOKING AND SIMULATE PAYMENT
# --------------------------------------------------

@router.post("/", status_code=201)
def create_booking(
    data: BookingCreate,
    current_user=Depends(require_roles("ATTENDEE"))
):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            # Lock the ticket category.
            # This prevents two users from buying the same
            # remaining tickets at the same time.
            cursor.execute(
                """
                SELECT
                    tc.id,
                    tc.event_id,
                    tc.category_name,
                    tc.price,
                    tc.quantity,
                    e.title AS event_title,
                    e.status AS event_status
                FROM ticket_categories tc
                JOIN events e ON e.id = tc.event_id
                WHERE tc.id = %s
                  AND tc.event_id = %s
                FOR UPDATE OF tc
                """,
                (data.category_id, data.event_id)
            )

            category = cursor.fetchone()

            if category is None:
                raise HTTPException(
                    status_code=404,
                    detail="Ticket category not found for this event"
                )

            # Only published events can be booked.
            if category["event_status"] != "PUBLISHED":
                raise HTTPException(
                    status_code=400,
                    detail="Tickets are available only for published events"
                )

            # Count tickets already sold.
            cursor.execute(
                """
                SELECT COUNT(*) AS sold_count
                FROM tickets
                WHERE category_id = %s
                  AND status IN ('VALID', 'USED')
                """,
                (data.category_id,)
            )

            sold_result = cursor.fetchone()
            sold_count = sold_result["sold_count"]

            available_tickets = (
                category["quantity"] - sold_count
            )

            # Check ticket availability.
            if data.quantity > available_tickets:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Not enough tickets available",
                        "available_tickets": available_tickets,
                        "requested_tickets": data.quantity
                    }
                )

            # Calculate total payment.
            total_amount = category["price"] * data.quantity

            # Create a pending booking.
            cursor.execute(
                """
                INSERT INTO bookings (
                    user_id,
                    event_id,
                    total_amount,
                    quantity,
                    status
                )
                VALUES (%s, %s, %s, %s, 'PENDING')
                RETURNING *
                """,
                (
                    current_user["id"],
                    data.event_id,
                    total_amount,
                    data.quantity
                )
            )

            booking = cursor.fetchone()

            # Simulate successful payment.
            # No real money is transferred.
            payment_reference = (
                "ES-" + secrets.token_urlsafe(12)
            )

            cursor.execute(
                """
                INSERT INTO payments (
                    booking_id,
                    payment_reference,
                    amount,
                    status,
                    paid_at
                )
                VALUES (%s, %s, %s, 'SUCCESS', NOW())
                RETURNING *
                """,
                (
                    booking["id"],
                    payment_reference,
                    total_amount
                )
            )

            payment = cursor.fetchone()

            # Confirm the booking after simulated payment.
            cursor.execute(
                """
                UPDATE bookings
                SET status = 'CONFIRMED'
                WHERE id = %s
                RETURNING *
                """,
                (booking["id"],)
            )

            confirmed_booking = cursor.fetchone()

            # Generate one unique QR token for each ticket.
            created_tickets = []

            for _ in range(data.quantity):

                qr_token = secrets.token_urlsafe(32)

                cursor.execute(
                    """
                    INSERT INTO tickets (
                        booking_id,
                        category_id,
                        qr_token,
                        status
                    )
                    VALUES (%s, %s, %s, 'VALID')
                    RETURNING id, booking_id, category_id,
                              qr_token, status
                    """,
                    (
                        booking["id"],
                        data.category_id,
                        qr_token
                    )
                )

                created_tickets.append(
                    cursor.fetchone()
                )

    return {
        "message": "Booking successful",
        "booking": confirmed_booking,
        "payment": {
            "payment_reference": payment["payment_reference"],
            "amount": payment["amount"],
            "status": payment["status"]
        },
        "tickets": created_tickets
    }


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
