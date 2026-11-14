from psycopg.types.json import Jsonb

from app.database import get_db_connection


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

        # Save the message before delivering it.
        self.log_message(message)

        receiver = self.agents.get(message.receiver)

        if receiver is None:
            raise ValueError(
                f"Receiver agent not found: {message.receiver}"
            )

        # Deliver through the message bus.
        return receiver.receive_message(message)