
from datetime import datetime, timedelta, timezone

from psycopg.errors import UniqueViolation

from app.database import get_db_connection
from app.agents.base_agent import BaseAgent
from app.agents.message import ACLMessage, Performative


class WaitlistAgent(BaseAgent):

    EXPIRY_DAYS = 7

    # -------------------------------------------------
    # RECEIVE ACL MESSAGE
    # -------------------------------------------------

    def receive_message(self, message: ACLMessage):

        # Return ACL responses to the caller without routing them again.
        if message.performative in {
            Performative.AGREE,
            Performative.REFUSE,
            Performative.PROPOSE,
            Performative.FAILURE
        }:
            return message

        action = message.content.get("action")

        # Handle INFORM messages.
        if message.performative == Performative.INFORM:

            if action == "TICKETS_AVAILABLE":
                return self.process_waitlist(message)

            if action == "EXPIRE_WAITLIST":
                return self.expire_waitlist(message)

            return self._reply(
                message,
                Performative.REFUSE,
                {
                    "reason": f"Unsupported INFORM action: {action}"
                }
            )

        # Handle REQUEST messages.
        if message.performative != Performative.REQUEST:
            return self._reply(
                message,
                Performative.REFUSE,
                {
                    "reason": "WaitlistAgent accepts REQUEST or INFORM messages."
                }
            )

        if action == "JOIN_WAITLIST":
            return self.join_waitlist(message)

        if action == "PROCESS_WAITLIST":
            return self.process_waitlist(message)

        if action == "EXPIRE_WAITLIST":
            return self.expire_waitlist(message)

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
    # VALIDATE WAITLIST REGISTRATION
    # -------------------------------------------------

    def _validate_join_request(self, content):

        try:
            user_id = int(content.get("user_id"))
            event_id = int(content.get("event_id"))
            quantity = int(content.get("quantity"))

        except (TypeError, ValueError):
            raise ValueError(
                "Valid user_id, event_id and quantity are required."
            )

        if user_id <= 0 or event_id <= 0:
            raise ValueError(
                "User ID and event ID must be positive."
            )

        if quantity < 1 or quantity > 10:
            raise ValueError(
                "Waitlist quantity must be between 1 and 10."
            )

        return user_id, event_id, quantity

    # -------------------------------------------------
    # VALIDATE EVENT ID
    # -------------------------------------------------

    def _validate_event_id(self, content):

        try:
            event_id = int(content.get("event_id"))

        except (TypeError, ValueError):
            raise ValueError("A valid event_id is required.")

        if event_id <= 0:
            raise ValueError("Event ID must be positive.")

        return event_id

    # -------------------------------------------------
    # JOIN WAITLIST
    # -------------------------------------------------

    def join_waitlist(self, message):

        try:
            user_id, event_id, quantity = self._validate_join_request(
                message.content
            )

            with get_db_connection() as connection:

                with connection.cursor() as cursor:

                    # Check attendee account.
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

                    if not cursor.fetchone():
                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": "Active attendee account not found."
                            }
                        )

                    # Check published event.
                    cursor.execute(
                        """
                        SELECT id
                        FROM events
                        WHERE id = %s
                          AND status = 'PUBLISHED'
                        """,
                        (event_id,)
                    )

                    if not cursor.fetchone():
                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": "Published event not found."
                            }
                        )

                    # A waitlist entry is valid only when no ticket category
                    # has enough remaining capacity for the requested quantity.
                    cursor.execute(
                        """
                        SELECT
                            SUM(
                                GREATEST(
                                    tc.quantity -
                                    COALESCE(s.sold_count, 0),
                                    0
                                )
                            ) AS remaining_quantity
                        FROM ticket_categories tc
                        LEFT JOIN (
                            SELECT category_id, COUNT(*) AS sold_count
                            FROM tickets
                            WHERE status IN ('VALID', 'USED')
                            GROUP BY category_id
                        ) s ON s.category_id = tc.id
                        WHERE tc.event_id = %s
                        """,
                        (event_id,)
                    )
                    availability = cursor.fetchone()

                    if (
                        availability is None
                        or int(availability["remaining_quantity"] or 0) < quantity
                    ):
                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": (
                                    "Tickets are still available. "
                                    "Please complete a booking instead."
                                )
                            }
                        )

                    # Prevent duplicate active waitlist entries.
                    cursor.execute(
                        """
                        SELECT id
                        FROM waitlist
                        WHERE user_id = %s
                          AND event_id = %s
                          AND status = 'WAITING'
                        """,
                        (user_id, event_id)
                    )

                    if cursor.fetchone():
                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": (
                                    "You are already on this event's waitlist."
                                )
                            }
                        )

                    # Insert waitlist entry.
                    cursor.execute(
                        """
                        INSERT INTO waitlist (
                            user_id,
                            event_id,
                            quantity,
                            status,
                            created_at
                        )
                        VALUES (%s, %s, %s, 'WAITING', NOW())
                        RETURNING id, created_at
                        """,
                        (user_id, event_id, quantity)
                    )

                    result = cursor.fetchone()

            self.state["last_join"] = {
                "waitlist_id": result["id"],
                "user_id": user_id,
                "event_id": event_id,
                "quantity": quantity
            }

            self.save_state()

            return self._reply(
                message,
                Performative.AGREE,
                {
                    "success": True,
                    "message": "Successfully joined the waitlist.",
                    "waitlist_id": result["id"],
                    "event_id": event_id,
                    "quantity": quantity,
                    "status": "WAITING"
                }
            )

        except UniqueViolation:
            return self._reply(
                message,
                Performative.REFUSE,
                {
                    "reason": (
                        "You are already on this event's waitlist."
                    )
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

    # -------------------------------------------------
    # PROCESS WAITLIST
    # -------------------------------------------------

    def process_waitlist(self, message):

        try:
            event_id = self._validate_event_id(message.content)

            processed = []
            while True:
                # Claim one FIFO entry and commit before calling BookingAgent.
                # BookingAgent uses a separate transaction, so holding this
                # row lock during the ACL call can deadlock on the FK check.
                with get_db_connection() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            SELECT id, user_id, quantity, created_at
                            FROM waitlist
                            WHERE event_id = %s
                              AND status = 'WAITING'
                            ORDER BY created_at ASC, id ASC
                            FOR UPDATE SKIP LOCKED
                            LIMIT 1
                            """,
                            (event_id,)
                        )
                        entry = cursor.fetchone()

                        if not entry:
                            break

                        cursor.execute(
                            """
                            SELECT id
                            FROM bookings
                            WHERE waitlist_id = %s
                              AND status = 'CONFIRMED'
                            ORDER BY id
                            LIMIT 1
                            """,
                            (entry["id"],)
                        )
                        existing_booking = cursor.fetchone()

                        if not existing_booking:
                            # Reconcile bookings created before waitlist_id
                            # was added to the bookings table.
                            cursor.execute(
                                """
                                SELECT id
                                FROM bookings
                                WHERE user_id = %s
                                  AND event_id = %s
                                  AND quantity = %s
                                  AND status = 'CONFIRMED'
                                  AND created_at >= %s
                                ORDER BY created_at, id
                                LIMIT 1
                                """,
                                (
                                    entry["user_id"],
                                    event_id,
                                    entry["quantity"],
                                    entry["created_at"]
                                )
                            )
                            existing_booking = cursor.fetchone()

                        if existing_booking:
                            cursor.execute(
                                """
                                UPDATE waitlist
                                SET status = 'FULFILLED'
                                WHERE id = %s
                                  AND status = 'WAITING'
                                """,
                                (entry["id"],)
                            )
                            self.message_bus.send(
                                ACLMessage(
                                    sender=self.name,
                                    receiver="NotificationAgent",
                                    performative=Performative.INFORM,
                                    conversation_id=message.conversation_id,
                                    content={
                                        "action": "SEND_NOTIFICATION",
                                        "user_id": entry["user_id"],
                                        "message": (
                                            "A waitlisted ticket became "
                                            "available and a booking was "
                                            "matched to your waitlist entry."
                                        )
                                    }
                                )
                            )
                            processed.append(
                                {
                                    "waitlist_id": entry["id"],
                                    "user_id": entry["user_id"],
                                    "status": "FULFILLED",
                                    "booking_id": existing_booking["id"],
                                    "idempotent": True
                                }
                            )
                            continue

                        cursor.execute(
                            """
                            SELECT
                                tc.id AS category_id,
                                tc.quantity -
                                COUNT(t.id) FILTER (
                                    WHERE t.status IN ('VALID', 'USED')
                                ) AS available_quantity
                            FROM ticket_categories tc
                            LEFT JOIN tickets t
                                ON t.category_id = tc.id
                            WHERE tc.event_id = %s
                            GROUP BY tc.id, tc.quantity
                            HAVING tc.quantity -
                                COUNT(t.id) FILTER (
                                    WHERE t.status IN ('VALID', 'USED')
                                ) >= %s
                            ORDER BY tc.id
                            LIMIT 1
                            """,
                            (event_id, entry["quantity"])
                        )
                        category = cursor.fetchone()

                        if not category:
                            break

                        cursor.execute(
                            """
                            UPDATE waitlist
                            SET status = 'OFFERED'
                            WHERE id = %s
                              AND status = 'WAITING'
                            """,
                            (entry["id"],)
                        )

                booking_message = ACLMessage(
                    sender=self.name,
                    receiver="BookingAgent",
                    performative=Performative.REQUEST,
                    conversation_id=message.conversation_id,
                    content={
                        "action": "CREATE_BOOKING",
                        "user_id": entry["user_id"],
                        "event_id": event_id,
                        "category_id": category["category_id"],
                        "quantity": entry["quantity"],
                        "waitlist_id": entry["id"]
                    }
                )

                try:
                    response = self.message_bus.send(booking_message)
                except Exception:
                    with get_db_connection() as connection:
                        with connection.cursor() as cursor:
                            cursor.execute(
                                """
                                UPDATE waitlist
                                SET status = 'WAITING'
                                WHERE id = %s
                                  AND status = 'OFFERED'
                                """,
                                (entry["id"],)
                            )
                    raise

                with get_db_connection() as connection:
                    with connection.cursor() as cursor:
                        if (
                            response
                            and response.performative == Performative.AGREE
                        ):
                            cursor.execute(
                                """
                                UPDATE waitlist
                                SET status = 'FULFILLED'
                                WHERE id = %s
                                  AND status = 'OFFERED'
                                """,
                                (entry["id"],)
                            )
                            self.message_bus.send(
                                ACLMessage(
                                    sender=self.name,
                                    receiver="NotificationAgent",
                                    performative=Performative.INFORM,
                                    conversation_id=message.conversation_id,
                                    content={
                                        "action": "SEND_NOTIFICATION",
                                        "user_id": entry["user_id"],
                                        "message": (
                                            "A ticket is available for your "
                                            "waitlisted event. Your waitlist "
                                            "booking has been created."
                                        )
                                    }
                                )
                            )
                            processed.append(
                                {
                                    "waitlist_id": entry["id"],
                                    "user_id": entry["user_id"],
                                    "status": "FULFILLED",
                                    "booking_id": response.content.get(
                                        "booking_id"
                                    )
                                }
                            )
                        else:
                            cursor.execute(
                                """
                                UPDATE waitlist
                                SET status = 'WAITING'
                                WHERE id = %s
                                  AND status = 'OFFERED'
                                """,
                                (entry["id"],)
                            )
                            break

            self.state["last_processing"] = {
                "event_id": event_id,
                "processed_count": len(processed)
            }

            self.save_state()

            return self._reply(
                message,
                Performative.AGREE,
                {
                    "success": True,
                    "event_id": event_id,
                    "processed_count": len(processed),
                    "processed_entries": processed
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

    # -------------------------------------------------
    # EXPIRE OLD WAITLIST ENTRIES
    # -------------------------------------------------

    def expire_waitlist(self, message):

        try:
            expiry_date = (
                datetime.now(timezone.utc)
                - timedelta(days=self.EXPIRY_DAYS)
            )

            with get_db_connection() as connection:

                with connection.cursor() as cursor:

                    cursor.execute(
                        """
                        UPDATE waitlist
                        SET status = 'EXPIRED'
                        WHERE status = 'WAITING'
                          AND created_at < %s
                        RETURNING id
                        """,
                        (expiry_date,)
                    )

                    expired_entries = cursor.fetchall()

            expired_count = len(expired_entries)

            self.state["last_expiry_sweep"] = {
                "expired_count": expired_count,
                "checked_at": datetime.now(timezone.utc).isoformat()
            }

            self.save_state()

            return self._reply(
                message,
                Performative.AGREE,
                {
                    "success": True,
                    "expired_count": expired_count
                }
            )

        except Exception as error:

            return self._reply(
                message,
                Performative.FAILURE,
                {
                    "reason": str(error)
                }
            )
