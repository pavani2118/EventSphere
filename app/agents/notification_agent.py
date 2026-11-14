
from app.database import get_db_connection
from app.agents.base_agent import BaseAgent
from app.agents.message import ACLMessage, Performative


class NotificationAgent(BaseAgent):

    def receive_message(self, message: ACLMessage):
        if message.performative != Performative.INFORM:
            return self._reply(
                message,
                Performative.REFUSE,
                {"reason": "NotificationAgent only accepts INFORM messages."}
            )

        action = message.content.get("action")

        if action == "SEND_NOTIFICATION":
            return self.send_notification(message)

        return self._reply(
            message,
            Performative.REFUSE,
            {"reason": f"Unsupported action: {action}"}
        )

    def _reply(self, request, performative, content):
        return self.send_message(
            receiver=request.sender,
            performative=performative,
            content=content,
            conversation_id=request.conversation_id
        )

    def send_notification(self, message):
        try:
            user_id = int(message.content.get("user_id"))
            notification_message = message.content.get("message")

            if user_id <= 0:
                raise ValueError("User ID must be positive.")

            if not isinstance(notification_message, str):
                raise ValueError("Notification message must be text.")

            notification_message = notification_message.strip()

            if not notification_message:
                raise ValueError("Notification message cannot be empty.")

            if len(notification_message) > 1000:
                raise ValueError("Notification message is too long.")

            with get_db_connection() as connection:
                with connection.cursor() as cursor:

                    cursor.execute("""
                        SELECT id
                        FROM users
                        WHERE id = %s
                          AND is_active = TRUE
                    """, (user_id,))

                    if not cursor.fetchone():
                        return self._reply(
                            message,
                            Performative.REFUSE,
                            {"reason": "Active user account not found."}
                        )

                    cursor.execute("""
                        INSERT INTO notifications (
                            user_id,
                            message,
                            is_read,
                            created_at
                        )
                        VALUES (%s, %s, FALSE, NOW())
                        RETURNING id, created_at
                    """, (user_id, notification_message))

                    result = cursor.fetchone()

            self.state["last_notification"] = {
                "notification_id": result["id"],
                "user_id": user_id,
                "message": notification_message
            }
            self.save_state()

            return self._reply(
                message,
                Performative.AGREE,
                {
                    "success": True,
                    "notification_id": result["id"],
                    "user_id": user_id,
                    "message": "Notification saved successfully."
                }
            )

        except (TypeError, ValueError) as error:
            return self._reply(
                message,
                Performative.REFUSE,
                {"reason": str(error)}
            )
