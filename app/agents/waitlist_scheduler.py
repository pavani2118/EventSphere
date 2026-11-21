import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from app.database import get_db_connection
from app.agents.message import ACLMessage, Performative

from app.agents.message import ACLMessage, Performative


logger = logging.getLogger(__name__)


def process_event_reminders(message_bus):
    try:
        now = datetime.now(timezone.utc)
        reminder_window_end = now + timedelta(hours=24)
        sent_count = 0

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        b.id AS booking_id,
                        b.user_id,
                        e.id AS event_id,
                        e.title AS event_title,
                        e.start_time
                    FROM bookings b
                    JOIN events e ON e.id = b.event_id
                    WHERE b.status = 'CONFIRMED'
                      AND e.status = 'PUBLISHED'
                      AND e.start_time >= %s
                      AND e.start_time <= %s
                    """,
                    (now, reminder_window_end)
                )
                upcoming = cursor.fetchall()

                for booking in upcoming:
                    reminder_message = (
                        f"Reminder: {booking['event_title']} starts soon "
                        f"(Event ID: {booking['event_id']}). "
                        f"Booking ID: {booking['booking_id']}."
                    )
                    cursor.execute(
                        """
                        SELECT id
                        FROM notifications
                        WHERE user_id = %s
                          AND message = %s
                        LIMIT 1
                        """,
                        (booking["user_id"], reminder_message)
                    )
                    if cursor.fetchone():
                        continue

                    response = message_bus.send(
                        ACLMessage(
                            sender="WaitlistScheduler",
                            receiver="NotificationAgent",
                            performative=Performative.INFORM,
                            content={
                                "action": "SEND_NOTIFICATION",
                                "user_id": booking["user_id"],
                                "message": reminder_message
                            }
                        )
                    )
                    if (
                        response
                        and response.performative == Performative.AGREE
                    ):
                        sent_count += 1

        return sent_count
    except Exception:
        logger.exception(
            "Event reminder sweep could not access the database."
        )
        return 0


async def waitlist_expiry_loop(message_bus, interval_seconds=None):

    # Default interval: 3600 seconds (1 hour).
    if interval_seconds is None:
        interval_seconds = int(
            os.getenv(
                "WAITLIST_EXPIRY_INTERVAL_SECONDS",
                "3600"
            )
        )

    if interval_seconds < 1:
        raise ValueError(
            "Scheduler interval must be at least 1 second."
        )

    while True:

        try:
            reminder_count = process_event_reminders(message_bus)
            if reminder_count:
                logger.info(
                    "Event reminder sweep completed. Sent: %s",
                    reminder_count
                )

            # Create an INFORM message for WaitlistAgent.
            message = ACLMessage(
                sender="WaitlistScheduler",
                receiver="WaitlistAgent",
                performative=Performative.INFORM,
                content={
                    "action": "EXPIRE_WAITLIST",
                    "trigger": "AUTOMATIC_SCHEDULE"
                }
            )

            # Run synchronous MessageBus operation in a worker thread.
            response = await asyncio.to_thread(
                message_bus.send,
                message
            )

            if (
                response
                and response.performative == Performative.AGREE
            ):

                expired_count = response.content.get(
                    "expired_count",
                    0
                )

                logger.info(
                    "Waitlist expiry completed. Expired entries: %s",
                    expired_count
                )

            else:
                logger.warning(
                    "Waitlist expiry was not completed successfully."
                )

        except asyncio.CancelledError:
            logger.info(
                "Waitlist expiry scheduler stopped."
            )
            raise

        except Exception:
            logger.exception(
                "Waitlist expiry scheduler encountered an error."
            )

        await asyncio.sleep(interval_seconds)