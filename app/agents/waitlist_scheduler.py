import asyncio
import logging
import os

from app.agents.message import ACLMessage, Performative


logger = logging.getLogger(__name__)


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