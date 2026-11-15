from abc import ABC, abstractmethod

from psycopg.types.json import Jsonb

from app.database import get_db_connection
from app.agents.message import ACLMessage, Performative


class BaseAgent(ABC):

    def __init__(self, name, message_bus):
        self.name = name
        self.message_bus = message_bus
        self.state = {}

    def send_message(
        self,
        receiver,
        performative,
        content,
        conversation_id=None
    ):

        message_data = {
            "sender": self.name,
            "receiver": receiver,
            "performative": performative,
            "content": content
        }

        if conversation_id:
            message_data["conversation_id"] = conversation_id

        message = ACLMessage(**message_data)

        return self.message_bus.send(message)

    def save_state(self):

        with get_db_connection() as connection:
            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    INSERT INTO agent_states (
                        agent_name,
                        state,
                        updated_at
                    )
                    VALUES (%s, %s, NOW())

                    ON CONFLICT (agent_name)

                    DO UPDATE SET
                        state = EXCLUDED.state,
                        updated_at = NOW()
                    """,
                    (
                        self.name,
                        Jsonb(self.state)
                    )
                )

    def load_state(self):

        with get_db_connection() as connection:
            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    SELECT state
                    FROM agent_states
                    WHERE agent_name = %s
                    """,
                    (self.name,)
                )

                result = cursor.fetchone()

        if result:
            self.state = result["state"]

        return self.state

    @abstractmethod
    def receive_message(self, message: ACLMessage):
        pass