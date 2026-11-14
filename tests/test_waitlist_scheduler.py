import asyncio
import queue

import pytest

from app.agents.message import ACLMessage, Performative
from app.agents.waitlist_scheduler import waitlist_expiry_loop


class FakeMessageBus:

    def __init__(self):
        self.messages = queue.Queue()

    def send(self, message):

        self.messages.put(message)

        return ACLMessage(
            sender="WaitlistAgent",
            receiver="WaitlistScheduler",
            performative=Performative.AGREE,
            conversation_id=message.conversation_id,
            content={
                "success": True,
                "expired_count": 2
            }
        )


def test_scheduler_sends_expiry_message_immediately():

    async def run_test():

        fake_bus = FakeMessageBus()

        task = asyncio.create_task(
            waitlist_expiry_loop(
                fake_bus,
                interval_seconds=60
            )
        )

        try:
            # Wait for the first message.
            message = await asyncio.to_thread(
                fake_bus.messages.get,
                True,
                3
            )

            assert message.sender == "WaitlistScheduler"
            assert message.receiver == "WaitlistAgent"

            assert message.performative == Performative.INFORM

            assert message.content["action"] == "EXPIRE_WAITLIST"

            assert (
                message.content["trigger"]
                == "AUTOMATIC_SCHEDULE"
            )

        finally:
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(run_test())


def test_scheduler_stops_when_cancelled():

    async def run_test():

        fake_bus = FakeMessageBus()

        task = asyncio.create_task(
            waitlist_expiry_loop(
                fake_bus,
                interval_seconds=60
            )
        )

        # Wait until the first message is sent.
        await asyncio.to_thread(
            fake_bus.messages.get,
            True,
            3
        )

        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert task.cancelled()

    asyncio.run(run_test())


def test_scheduler_rejects_invalid_interval():

    fake_bus = FakeMessageBus()

    with pytest.raises(ValueError):

        asyncio.run(
            waitlist_expiry_loop(
                fake_bus,
                interval_seconds=0
            )
        )


def test_scheduler_rejects_negative_interval():

    fake_bus = FakeMessageBus()

    with pytest.raises(ValueError):

        asyncio.run(
            waitlist_expiry_loop(
                fake_bus,
                interval_seconds=-10
            )
        )