
from datetime import datetime

from app.database import get_db_connection
from app.agents.base_agent import BaseAgent
from app.agents.message import ACLMessage, Performative


class TicketAgent(BaseAgent):
    """
    Validates digital tickets and manages one-time event check-in.
    """

    # -------------------------------------------------
    # RECEIVE ACL MESSAGE
    # -------------------------------------------------

    def receive_message(self, message: ACLMessage):

        if message.performative != Performative.REQUEST:
            return self._reply(
                message,
                Performative.REFUSE,
                {
                    "reason": "TicketAgent only accepts REQUEST messages."
                }
            )

        action = message.content.get("action")

        if action == "CHECK_IN":
            return self.check_in(message)

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

    def _validate_request(self, content):

        qr_token = content.get("qr_token")
        staff_user_id = content.get("staff_user_id")

        if not isinstance(qr_token, str):
            raise ValueError("A valid QR token is required.")

        qr_token = qr_token.strip()

        if len(qr_token) < 20 or len(qr_token) > 200:
            raise ValueError("Invalid QR token length.")

        try:
            staff_user_id = int(staff_user_id)

        except (TypeError, ValueError):
            raise ValueError("A valid staff user ID is required.")

        if staff_user_id <= 0:
            raise ValueError("Invalid staff user ID.")

        return qr_token, staff_user_id

    # -------------------------------------------------
    # CHECK-IN
    # -------------------------------------------------

    def check_in(self, message):

        try:

            qr_token, staff_user_id = self._validate_request(
                message.content
            )

            with get_db_connection() as connection:

                with connection.cursor() as cursor:

                    # Verify active staff member.
                    cursor.execute(
                        """
                        SELECT id, role
                        FROM users
                        WHERE id = %s
                          AND is_active = TRUE
                          AND role IN ('ADMIN', 'GATE_STAFF')
                        """,
                        (staff_user_id,)
                    )

                    staff = cursor.fetchone()

                    if not staff:

                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": (
                                    "Only active gate staff or admins "
                                    "can check in tickets."
                                )
                            }
                        )

                    # Lock ticket row to prevent double check-in.
                    cursor.execute(
                        """
                        SELECT
                            t.id AS ticket_id,
                            t.status AS ticket_status,
                            t.booking_id,
                            e.id AS event_id,
                            e.title AS event_title,
                            e.status AS event_status,
                            b.status AS booking_status,
                            tc.category_name,
                            u.full_name AS attendee_name,
                            p.status AS payment_status

                        FROM tickets t

                        JOIN bookings b
                            ON b.id = t.booking_id

                        JOIN events e
                            ON e.id = b.event_id

                        JOIN ticket_categories tc
                            ON tc.id = t.category_id

                        JOIN users u
                            ON u.id = b.user_id

                        LEFT JOIN LATERAL (
                            SELECT status
                            FROM payments
                            WHERE booking_id = b.id
                            ORDER BY id DESC
                            LIMIT 1
                        ) p ON TRUE

                        WHERE t.qr_token = %s

                        FOR UPDATE OF t
                        """,
                        (qr_token,)
                    )

                    ticket = cursor.fetchone()

                    # Ticket not found.
                    if not ticket:

                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": (
                                    "Invalid QR ticket. "
                                    "Ticket not found."
                                )
                            }
                        )

                    # Already used ticket.
                    if ticket["ticket_status"] == "USED":

                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": (
                                    "Ticket has already been used."
                                ),
                                "ticket_id": ticket["ticket_id"]
                            }
                        )

                    # Cancelled ticket.
                    if ticket["ticket_status"] == "CANCELLED":

                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": (
                                    "This ticket has been cancelled."
                                )
                            }
                        )

                    # Invalid ticket status.
                    if ticket["ticket_status"] != "VALID":

                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": "Ticket is not valid."
                            }
                        )

                    # Booking must be confirmed.
                    if ticket["booking_status"] != "CONFIRMED":

                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": "Booking is not confirmed."
                            }
                        )

                    # Payment must be successful.
                    if ticket["payment_status"] != "SUCCESS":

                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": (
                                    "Payment has not completed successfully."
                                ),
                                "result": "PAYMENT_NOT_COMPLETED"
                            }
                        )

                    # Event must not be cancelled.
                    if ticket["event_status"] != "PUBLISHED":

                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": (
                                    "This event is not published and valid "
                                    "for check-in."
                                ),
                                "result": "EVENT_NOT_VALID"
                            }
                        )

                    # Update ticket status.
                    cursor.execute(
                        """
                        UPDATE tickets

                        SET
                            status = 'USED',
                            checked_in_at = NOW(),
                            checked_in_by = %s

                        WHERE id = %s
                          AND status = 'VALID'

                        RETURNING id, checked_in_at
                        """,
                        (
                            staff_user_id,
                            ticket["ticket_id"]
                        )
                    )

                    checked_ticket = cursor.fetchone()

                    if not checked_ticket:

                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {
                                "reason": (
                                    "Ticket check-in failed. "
                                    "It may already have been used."
                                )
                            }
                        )

            # -----------------------------------------
            # SAVE AGENT STATE
            # -----------------------------------------

            checked_in_at = (
                checked_ticket["checked_in_at"].isoformat()
                if checked_ticket["checked_in_at"]
                else None
            )

            self.state["last_check_in"] = {
                "ticket_id": ticket["ticket_id"],
                "event_id": ticket["event_id"],
                "staff_user_id": staff_user_id,
                "status": "SUCCESS",
                "checked_in_at": checked_in_at
            }

            self.save_state()

            # -----------------------------------------
            # SEND SUCCESS RESPONSE
            # -----------------------------------------

            return self._reply(
                message,
                Performative.AGREE,
                {
                    "success": True,
                    "message": "Ticket check-in successful.",
                    "ticket_id": ticket["ticket_id"],
                    "event_id": ticket["event_id"],
                    "event_title": ticket["event_title"],
                    "category": ticket["category_name"],
                    "attendee_name": ticket["attendee_name"],
                    "ticket_status": "USED",
                    "checked_in_by": staff_user_id,
                    "checked_in_at": checked_in_at
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
