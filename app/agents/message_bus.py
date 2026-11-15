import logging

from psycopg.types.json import Jsonb

from app.database import get_db_connection
from app.agents.message import ACLMessage, Performative


logger = logging.getLogger(__name__)


class MessageBus:

    def __init__(self):
        self.agents = {}

    def register(self, agent):

        if agent.name in self.agents:
            raise ValueError(
                f"Agent already registered: {agent.name}"
            )

        self.agents[agent.name] = agent

    def log_message(self, message):

        with get_db_connection() as connection:
            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    INSERT INTO agent_messages (
                        sender,
                        receiver,
                        performative,
                        content,
                        conversation_id,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        message.sender,
                        message.receiver,
                        message.performative.value,
                        Jsonb(message.content),
                        message.conversation_id
                    )
                )

    def send(self, message):

        receiver = self.agents.get(message.receiver)

        if receiver is None:
            raise ValueError(
                f"Receiver agent not found: {message.receiver}"
            )

        # Save the message before delivering it.
        self.log_message(message)

        # Deliver through the message bus.
        try:
            return receiver.receive_message(message)
        except Exception:
            logger.exception(
                "Agent %s failed to process a message.",
                message.receiver
            )
            return ACLMessage(
                sender=message.receiver,
                receiver=message.sender,
                performative=Performative.FAILURE,
                conversation_id=message.conversation_id,
                content={
                    "reason": (
                        f"{message.receiver} could not process the "
                        "message."
                    )
                }
            )