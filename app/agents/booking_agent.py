
import secrets
from datetime import datetime

from app.database import get_db_connection
from app.agents.base_agent import BaseAgent
from app.agents.message import ACLMessage, Performative


class BookingAgent(BaseAgent):
    """
    Handles ticket booking requests, inventory validation,
    simulated payments and digital ticket generation.
    """

    MAX_TICKETS_PER_BOOKING = 10

    def receive_message(self, message: ACLMessage):
        if message.performative != Performative.REQUEST:
            return self._reply(
                message,
                Performative.REFUSE,
                {"reason": "BookingAgent only accepts REQUEST messages."}
            )

        action = message.content.get("action")

        if action == "CREATE_BOOKING":
            return self.create_booking(message)

        return self._reply(
            message,
            Performative.REFUSE,
            {"reason": f"Unsupported action: {action}"}
        )

    # -------------------------------------------------
    # ACL REPLY
    # -------------------------------------------------

    def _reply(self, request, performative, content):
        return self.send_message(
            receiver=request.sender,
            performative=performative,
            content=content,
            conversation_id=request.conversation_id
        )

    # -------------------------------------------------
    # REQUEST VALIDATION
    # -------------------------------------------------

    def _validate_booking_request(self, content):
        try:
            user_id = int(content["user_id"])
            event_id = int(content["event_id"])
            category_id = int(content["category_id"])
            quantity = int(content["quantity"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                "user_id, event_id, category_id and quantity must be valid integers."
            )

        if user_id <= 0:
            raise ValueError("Invalid user_id.")

        if event_id <= 0:
            raise ValueError("Invalid event_id.")

        if category_id <= 0:
            raise ValueError("Invalid category_id.")

        if quantity <= 0:
            raise ValueError("Booking quantity must be greater than zero.")

        if quantity > self.MAX_TICKETS_PER_BOOKING:
            raise ValueError(
                f"A maximum of {self.MAX_TICKETS_PER_BOOKING} tickets "
                "can be booked at once."
            )

        return user_id, event_id, category_id, quantity

    # -------------------------------------------------
    # CREATE BOOKING
    # -------------------------------------------------

    def create_booking(self, message):
        try:
            content = message.content

            user_id, event_id, category_id, quantity = (
                self._validate_booking_request(content)
            )

            with get_db_connection() as connection:
                with connection.cursor() as cursor:

                    # Lock the ticket category row.
                    # This prevents concurrent transactions from
                    # overselling the same ticket category.
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
                        (category_id, event_id)
                    )

                    category = cursor.fetchone()

                    if not category:
                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {"reason": "Ticket category or event not found."}
                        )

                    # Only published events can receive bookings.
                    if category["event_status"] != "PUBLISHED":
                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {"reason": "This event is not available for booking."}
                        )

                    # Check available ticket inventory.
                    cursor.execute(
                        """
                        SELECT COUNT(*) AS sold_count
                        FROM tickets
                        WHERE category_id = %s
                          AND status IN ('VALID', 'USED')
                        """,
                        (category_id,)
                    )

                    sold_count = cursor.fetchone()["sold_count"]
                    available_quantity = category["quantity"] - sold_count

                    if quantity > available_quantity:
                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": "Not enough tickets available.",
                                "requested_quantity": quantity,
                                "available_quantity": max(
                                    available_quantity, 0
                                )
                            }
                        )

                    # Check attendee exists and is active.
                    cursor.execute(
                        """
                        SELECT id
                        FROM users
                        WHERE id = %s
                          AND is_active = TRUE
                        """,
                        (user_id,)
                    )

                    attendee = cursor.fetchone()

                    if not attendee:
                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {"reason": "Attendee account not found or inactive."}
                        )

                    # Calculate booking amount.
                    total_amount = category["price"] * quantity

                    # Create booking.
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
                        RETURNING id
                        """,
                        (
                            user_id,
                            event_id,
                            total_amount,
                            quantity
                        )
                    )

                    booking = cursor.fetchone()
                    booking_id = booking["id"]

                    # Simulated payment reference.
                    payment_reference = (
                        "ES-" + secrets.token_hex(8).upper()
                    )

                    # Create simulated successful payment.
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
                        RETURNING id
                        """,
                        (
                            booking_id,
                            payment_reference,
                            total_amount
                        )
                    )

                    # Confirm booking after simulated payment.
                    cursor.execute(
                        """
                        UPDATE bookings
                        SET status = 'CONFIRMED'
                        WHERE id = %s
                        """,
                        (booking_id,)
                    )

                    # Generate one unique QR token per ticket.
                    ticket_ids = []

                    for _ in range(quantity):
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
                            RETURNING id
                            """,
                            (
                                booking_id,
                                category_id,
                                qr_token
                            )
                        )

                        ticket = cursor.fetchone()
                        ticket_ids.append({
                            "ticket_id": ticket["id"],
                            "qr_token": qr_token
                        })

            # Save persistent agent state after successful transaction.
            self.state["last_booking"] = {
                "booking_id": booking_id,
                "event_id": event_id,
                "user_id": user_id,
                "quantity": quantity,
                "status": "CONFIRMED",
                "processed_at": datetime.now().astimezone().isoformat()
            }

            self.save_state()

            return self._reply(
                message,
                Performative.AGREE,
                {
                    "booking_id": booking_id,
                    "event_id": event_id,
                    "event_title": category["event_title"],
                    "category_id": category_id,
                    "category_name": category["category_name"],
                    "quantity": quantity,
                    "total_amount": str(total_amount),
                    "currency": "LKR",
                    "booking_status": "CONFIRMED",
                    "payment_status": "SUCCESS",
                    "payment_reference": payment_reference,
                    "tickets": ticket_ids
                }
            )

        except (KeyError, TypeError, ValueError) as error:
            return self._reply(
                message,
                Performative.REFUSE,
                {"reason": str(error)}
            )
