
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

        if action == "PROCESS_PAYMENT":
            return self.process_payment(message)

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

    def process_payment(self, message):
        try:
            booking_id = int(message.content["booking_id"])
            user_id = int(message.content["user_id"])
            category_id = int(message.content["category_id"])
            payment_result = str(
                message.content["payment_result"]
            ).upper()
        except (KeyError, TypeError, ValueError):
            return self._reply(
                message,
                Performative.REFUSE,
                {"reason": "Valid booking ID and payment result are required."}
            )

        if booking_id <= 0 or user_id <= 0:
            return self._reply(
                message,
                Performative.REFUSE,
                {"reason": "Booking ID and user ID must be positive."}
            )

        if payment_result not in {"SUCCESS", "FAILED"}:
            return self._reply(
                message,
                Performative.REFUSE,
                {"reason": "Payment result must be SUCCESS or FAILED."}
            )

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        b.id,
                        b.user_id,
                        b.event_id,
                        b.quantity,
                        b.total_amount,
                        b.status AS booking_status,
                        e.title AS event_title,
                        p.id AS payment_id,
                        p.status AS payment_status,
                        p.payment_reference
                    FROM bookings b
                    JOIN events e ON e.id = b.event_id
                    LEFT JOIN LATERAL (
                        SELECT id, status, payment_reference
                        FROM payments
                        WHERE booking_id = b.id
                        ORDER BY id DESC
                        LIMIT 1
                    ) p ON TRUE
                    WHERE b.id = %s
                    FOR UPDATE OF b
                    """,
                    (booking_id,)
                )
                booking = cursor.fetchone()

                if not booking:
                    return self._reply(
                        message,
                        Performative.REFUSE,
                        {"reason": "Booking not found."}
                    )

                if booking["user_id"] != user_id:
                    return self._reply(
                        message,
                        Performative.REFUSE,
                        {"reason": "You can only process your own booking."}
                    )

                if booking["booking_status"] == "CONFIRMED":
                    return self._reply(
                        message,
                        Performative.AGREE,
                        {
                            "success": True,
                            "booking_id": booking_id,
                            "booking_status": "CONFIRMED",
                            "payment_status": "SUCCESS",
                            "idempotent": True
                        }
                    )

                if booking["payment_status"] == "SUCCESS":
                    return self._reply(
                        message,
                        Performative.AGREE,
                        {
                            "success": True,
                            "booking_id": booking_id,
                            "booking_status": "CONFIRMED",
                            "payment_status": "SUCCESS",
                            "idempotent": True
                        }
                    )

                if payment_result == "FAILED":
                    cursor.execute(
                        """
                        UPDATE payments
                        SET status = 'FAILED',
                            paid_at = NULL
                        WHERE id = %s
                          AND status != 'FAILED'
                        """,
                        (booking["payment_id"],)
                    )
                    return self._reply(
                        message,
                        Performative.AGREE,
                        {
                            "success": True,
                            "booking_id": booking_id,
                            "booking_status": "PENDING",
                            "payment_status": "FAILED",
                            "payment_reference": booking["payment_reference"],
                            "tickets": [],
                            "idempotent": True
                        }
                    )

                cursor.execute(
                    """
                    SELECT COUNT(*) AS ticket_count
                    FROM tickets
                    WHERE booking_id = %s
                    """,
                    (booking_id,)
                )
                ticket_count = cursor.fetchone()["ticket_count"]

                if ticket_count > 0:
                    cursor.execute(
                        """
                        UPDATE payments
                        SET status = 'SUCCESS',
                            paid_at = NOW()
                        WHERE id = %s
                        """,
                        (booking["payment_id"],)
                    )
                    cursor.execute(
                        """
                        UPDATE bookings
                        SET status = 'CONFIRMED'
                        WHERE id = %s
                        """,
                        (booking_id,)
                    )
                    return self._reply(
                        message,
                        Performative.AGREE,
                        {
                            "success": True,
                            "booking_id": booking_id,
                            "booking_status": "CONFIRMED",
                            "payment_status": "SUCCESS",
                            "payment_reference": booking["payment_reference"],
                            "tickets": [],
                            "idempotent": True
                        }
                    )

                cursor.execute(
                    """
                    SELECT category_id
                    FROM ticket_categories
                    WHERE id = %s
                      AND event_id = %s
                    LIMIT 1
                    """,
                        (category_id, booking["event_id"])
                )
                category = cursor.fetchone()

                if not category:
                    return self._reply(
                        message,
                        Performative.REFUSE,
                        {"reason": "Ticket category not found."}
                    )

                cursor.execute(
                    """
                    SELECT id
                    FROM ticket_categories
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (category["category_id"],)
                )

                cursor.execute(
                    """
                    SELECT
                        tc.quantity -
                        COUNT(t.id) FILTER (
                            WHERE t.status IN ('VALID', 'USED')
                        ) AS available_quantity
                    FROM ticket_categories tc
                    LEFT JOIN tickets t ON t.category_id = tc.id
                    WHERE tc.id = %s
                    GROUP BY tc.id, tc.quantity
                    """,
                    (category["category_id"],)
                )
                availability = cursor.fetchone()

                if (
                    not availability
                    or int(availability["available_quantity"]) < int(
                        booking["quantity"]
                    )
                ):
                    return self._reply(
                        message,
                        Performative.REFUSE,
                        {"reason": "Not enough tickets are available."}
                    )

                cursor.execute(
                    """
                    UPDATE payments
                    SET status = 'SUCCESS',
                        paid_at = NOW()
                    WHERE id = %s
                      AND status != 'SUCCESS'
                    """,
                    (booking["payment_id"],)
                )

                cursor.execute(
                    """
                    UPDATE bookings
                    SET status = 'CONFIRMED'
                    WHERE id = %s
                      AND status = 'PENDING'
                    """,
                    (booking_id,)
                )

                ticket_ids = []
                for _ in range(int(booking["quantity"])):
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
                            category["category_id"],
                            qr_token
                        )
                    )
                    ticket = cursor.fetchone()
                    ticket_ids.append({
                        "ticket_id": ticket["id"],
                        "qr_token": qr_token
                    })

        self.state["last_payment"] = {
            "booking_id": booking_id,
            "payment_status": "SUCCESS",
            "processed_at": datetime.now().astimezone().isoformat()
        }
        self.save_state()

        return self._reply(
            message,
            Performative.AGREE,
            {
                "success": True,
                "booking_id": booking_id,
                "event_title": booking["event_title"],
                "booking_status": "CONFIRMED",
                "payment_status": "SUCCESS",
                "payment_reference": booking["payment_reference"],
                "tickets": ticket_ids
            }
        )

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

            payment_result = str(
                content.get("payment_result", "SUCCESS")
            ).upper()

            if payment_result not in {"SUCCESS", "FAILED"}:
                return self._reply(
                    message,
                    Performative.REFUSE,
                    {"reason": "Payment result must be SUCCESS or FAILED."}
                )

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
                        VALUES (
                            %s,
                            %s,
                            %s,
                            %s,
                            CASE WHEN %s = 'SUCCESS' THEN NOW() ELSE NULL END
                        )
                        RETURNING id
                        """,
                        (
                            booking_id,
                            payment_reference,
                            total_amount,
                            payment_result,
                            payment_result
                        )
                    )
                    ticket_ids = []

                    if payment_result == "SUCCESS":
                        cursor.execute(
                            """
                            UPDATE bookings
                            SET status = 'CONFIRMED'
                            WHERE id = %s
                            """,
                            (booking_id,)
                        )

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

            # -----------------------------------------
            # DATABASE TRANSACTION COMPLETED
            # -----------------------------------------

            # Save BookingAgent state.
            self.state["last_booking"] = {
                "booking_id": booking_id,
                "event_id": event_id,
                "user_id": user_id,
                "quantity": quantity,
                "status": (
                    "CONFIRMED"
                    if payment_result == "SUCCESS"
                    else "PENDING"
                ),
                "payment_status": payment_result,
                "processed_at": (
                    datetime.now().astimezone().isoformat()
                )
            }

            self.save_state()

            # -----------------------------------------
            # NOTIFY ATTENDEE THROUGH NOTIFICATION AGENT
            # -----------------------------------------

            if payment_result == "SUCCESS":
                notification_status = self.send_booking_notification(
                    user_id=user_id,
                    booking_id=booking_id,
                    event_title=category["event_title"],
                    quantity=quantity,
                    total_amount=total_amount,
                    payment_reference=payment_reference
                )
            else:
                try:
                    self.send_message(
                        receiver="NotificationAgent",
                        performative=Performative.INFORM,
                        content={
                            "action": "SEND_NOTIFICATION",
                            "user_id": user_id,
                            "message": (
                                f"Your payment for {category['event_title']} "
                                f"failed. Booking ID: {booking_id}. "
                                f"No tickets have been issued."
                            )
                        }
                    )
                    notification_status = "SENT"
                except Exception:
                    notification_status = "FAILED"

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
                    "booking_status": (
                        "CONFIRMED"
                        if payment_result == "SUCCESS"
                        else "PENDING"
                    ),
                    "payment_status": payment_result,
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
