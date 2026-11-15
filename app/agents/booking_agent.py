
import secrets
from datetime import datetime

from app.database import get_db_connection
from app.agents.base_agent import BaseAgent
from app.agents.message import ACLMessage, Performative


class BookingAgent(BaseAgent):
    """
    Handles ticket booking requests, simulated payments,
    digital ticket generation and attendee notifications.
    """

    MAX_TICKETS_PER_BOOKING = 10

    # -------------------------------------------------
    # RECEIVE ACL MESSAGE
    # -------------------------------------------------

    def receive_message(self, message: ACLMessage):

        # Ignore ACL response messages.
        # Do not send another response to a response.
        if message.performative in {
            Performative.AGREE,
            Performative.REFUSE,
            Performative.PROPOSE,
            Performative.FAILURE
        }:
            return message

        if message.performative != Performative.REQUEST:
            return self._reply(
                message,
                Performative.REFUSE,
                {
                    "reason": "BookingAgent only accepts REQUEST messages."
                }
            )

        action = message.content.get("action")

        if action == "CREATE_BOOKING":
            return self.create_booking(message)

        return self._reply(
            message,
            Performative.REFUSE,
            {
                "reason": f"Unsupported action: {action}"
            }
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
                "user_id, event_id, category_id and quantity "
                "must be valid integers."
            )

        if user_id <= 0:
            raise ValueError("Invalid user_id.")

        if event_id <= 0:
            raise ValueError("Invalid event_id.")

        if category_id <= 0:
            raise ValueError("Invalid category_id.")

        if quantity <= 0:
            raise ValueError(
                "Booking quantity must be greater than zero."
            )

        if quantity > self.MAX_TICKETS_PER_BOOKING:
            raise ValueError(
                f"A maximum of {self.MAX_TICKETS_PER_BOOKING} "
                "tickets can be booked at once."
            )

        waitlist_id = content.get("waitlist_id")

        if waitlist_id is not None:
            try:
                waitlist_id = int(waitlist_id)
            except (TypeError, ValueError):
                raise ValueError("Invalid waitlist_id.")

            if waitlist_id <= 0:
                raise ValueError("Invalid waitlist_id.")

        return user_id, event_id, category_id, quantity, waitlist_id

    # -------------------------------------------------
    # SEND NOTIFICATION
    # -------------------------------------------------

    def send_booking_notification(
        self,
        user_id,
        booking_id,
        event_title,
        quantity,
        total_amount,
        payment_reference
    ):

        notification_message = (
            f"Your booking for {event_title} has been confirmed. "
            f"Booking ID: {booking_id}. "
            f"Tickets: {quantity}. "
            f"Total amount: LKR {total_amount}. "
            f"Payment reference: {payment_reference}."
        )

        try:
            self.send_message(
                receiver="NotificationAgent",
                performative=Performative.INFORM,
                content={
                    "action": "SEND_NOTIFICATION",
                    "user_id": user_id,
                    "message": notification_message
                }
            )

            return "SENT"

        except Exception:
            # A notification failure must not cancel
            # an already successful booking.
            return "FAILED"

    # -------------------------------------------------
    # CREATE BOOKING
    # -------------------------------------------------

    def create_booking(self, message):

        try:
            content = message.content

            (
                user_id,
                event_id,
                category_id,
                quantity,
                waitlist_id
            ) = self._validate_booking_request(content)

            # -----------------------------------------
            # DATABASE TRANSACTION
            # -----------------------------------------

            with get_db_connection() as connection:

                with connection.cursor() as cursor:

                    if waitlist_id is not None:
                        cursor.execute(
                            """
                            SELECT id, status, quantity, total_amount
                            FROM bookings
                            WHERE waitlist_id = %s
                            FOR UPDATE
                            """,
                            (waitlist_id,)
                        )

                        existing_booking = cursor.fetchone()

                        if existing_booking:
                            if existing_booking["status"] != "CONFIRMED":
                                return self._reply(
                                    message,
                                    Performative.REFUSE,
                                    {
                                        "reason": (
                                            "The waitlist booking is not "
                                            "confirmed."
                                        )
                                    }
                                )

                            return self._reply(
                                message,
                                Performative.AGREE,
                                {
                                    "booking_id": existing_booking["id"],
                                    "event_id": event_id,
                                    "quantity": existing_booking["quantity"],
                                    "total_amount": str(
                                        existing_booking["total_amount"]
                                    ),
                                    "booking_status": "CONFIRMED",
                                    "idempotent": True
                                }
                            )

                    # Lock ticket category to prevent
                    # concurrent bookings from overselling.
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
                            {
                                "reason": (
                                    "Ticket category or event not found."
                                )
                            }
                        )

                    # Check event publication status.
                    if category["event_status"] != "PUBLISHED":

                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": (
                                    "This event is not available for booking."
                                )
                            }
                        )

                    # ---------------------------------
                    # CHECK TICKET AVAILABILITY
                    # ---------------------------------

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

                    available_quantity = (
                        category["quantity"] - sold_count
                    )

                    if quantity > available_quantity:

                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": (
                                    "Not enough tickets available."
                                ),
                                "requested_quantity": quantity,
                                "available_quantity": max(
                                    available_quantity, 0
                                )
                            }
                        )

                    # ---------------------------------
                    # CHECK ATTENDEE
                    # ---------------------------------

                    cursor.execute(
                        """
                        SELECT id
                        FROM users
                        WHERE id = %s
                          AND role = 'ATTENDEE'
                          AND is_active = TRUE
                        """,
                        (user_id,)
                    )

                    attendee = cursor.fetchone()

                    if not attendee:

                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": (
                                    "Attendee account not found or inactive."
                                )
                            }
                        )

                    # ---------------------------------
                    # CALCULATE TOTAL AMOUNT
                    # ---------------------------------

                    total_amount = category["price"] * quantity

                    # ---------------------------------
                    # CREATE BOOKING
                    # ---------------------------------

                    cursor.execute(
                        """
                        INSERT INTO bookings (
                            user_id,
                            event_id,
                            total_amount,
                            quantity,
                            status,
                            waitlist_id
                        )
                        VALUES (%s, %s, %s, %s, 'PENDING', %s)
                        ON CONFLICT (waitlist_id)
                            WHERE waitlist_id IS NOT NULL
                            DO NOTHING
                        RETURNING id
                        """,
                        (
                            user_id,
                            event_id,
                            total_amount,
                            quantity,
                            waitlist_id
                        )
                    )

                    booking = cursor.fetchone()

                    if booking is None:
                        cursor.execute(
                            """
                            SELECT id, status, quantity, total_amount
                            FROM bookings
                            WHERE waitlist_id = %s
                            """,
                            (waitlist_id,)
                        )
                        booking = cursor.fetchone()

                        if not booking:
                            return self._reply(
                                message,
                                Performative.FAILURE,
                                {
                                    "reason": (
                                        "Waitlist booking could not be "
                                        "created or recovered."
                                    )
                                }
                            )

                        return self._reply(
                            message,
                            Performative.AGREE,
                            {
                                "booking_id": booking["id"],
                                "event_id": event_id,
                                "quantity": booking["quantity"],
                                "total_amount": str(
                                    booking["total_amount"]
                                ),
                                "booking_status": booking["status"],
                                "idempotent": True
                            }
                        )

                    booking_id = booking["id"]

                    # ---------------------------------
                    # SIMULATED PAYMENT
                    # ---------------------------------

                    payment_reference = (
                        "ES-" + secrets.token_hex(8).upper()
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
                        RETURNING id
                        """,
                        (
                            booking_id,
                            payment_reference,
                            total_amount
                        )
                    )

                    # ---------------------------------
                    # CONFIRM BOOKING
                    # ---------------------------------

                    cursor.execute(
                        """
                        UPDATE bookings
                        SET status = 'CONFIRMED'
                        WHERE id = %s
                        """,
                        (booking_id,)
                    )

                    # ---------------------------------
                    # GENERATE DIGITAL TICKETS
                    # ---------------------------------

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

                        ticket_ids.append(
                            {
                                "ticket_id": ticket["id"],
                                "qr_token": qr_token
                            }
                        )

            # -----------------------------------------
            # DATABASE TRANSACTION COMPLETED
            # -----------------------------------------

            # Save BookingAgent state.
            self.state["last_booking"] = {
                "booking_id": booking_id,
                "event_id": event_id,
                "user_id": user_id,
                "quantity": quantity,
                "status": "CONFIRMED",
                "processed_at": (
                    datetime.now().astimezone().isoformat()
                )
            }

            self.save_state()

            # -----------------------------------------
            # NOTIFY ATTENDEE THROUGH NOTIFICATION AGENT
            # -----------------------------------------

            notification_status = self.send_booking_notification(
                user_id=user_id,
                booking_id=booking_id,
                event_title=category["event_title"],
                quantity=quantity,
                total_amount=total_amount,
                payment_reference=payment_reference
            )

            # Update state with notification result.
            self.state["last_booking"]["notification_status"] = (
                notification_status
            )

            self.save_state()

            # -----------------------------------------
            # SEND SUCCESSFUL BOOKING RESPONSE
            # -----------------------------------------

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
                    "notification_status": notification_status,
                    "tickets": ticket_ids
                }
            )

        except (KeyError, TypeError, ValueError) as error:

            return self._reply(
                message,
                Performative.REFUSE,
                {
                    "reason": str(error)
                }
            )
