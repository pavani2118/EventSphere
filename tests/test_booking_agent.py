
from app.agents.booking_agent import BookingAgent
from app.agents.message import ACLMessage, Performative


class FakeMessageBus:
    def __init__(self):
        self.sent_messages = []

    def send(self, message):
        self.sent_messages.append(message)
        return message


def create_agent():
    bus = FakeMessageBus()
    agent = BookingAgent("BookingAgent", bus)
    return agent, bus


def test_booking_agent_rejects_unknown_action():
    agent, bus = create_agent()

    message = ACLMessage(
        sender="BookingAPI",
        receiver="BookingAgent",
        performative=Performative.REQUEST,
        content={"action": "UNKNOWN_ACTION"}
    )

    agent.receive_message(message)

    assert len(bus.sent_messages) == 1
    assert bus.sent_messages[0].performative == Performative.REFUSE
    assert "Unsupported action" in bus.sent_messages[0].content["reason"]


def test_booking_agent_rejects_quantity_above_limit():
    agent, bus = create_agent()

    message = ACLMessage(
        sender="BookingAPI",
        receiver="BookingAgent",
        performative=Performative.REQUEST,
        content={
            "action": "CREATE_BOOKING",
            "user_id": 1,
            "event_id": 1,
            "category_id": 1,
            "quantity": 11
        }
    )

    agent.receive_message(message)

    assert len(bus.sent_messages) == 1
    assert bus.sent_messages[0].performative == Performative.REFUSE
    assert "maximum of 10 tickets" in bus.sent_messages[0].content["reason"]


def test_booking_agent_rejects_zero_quantity():
    agent, bus = create_agent()

    message = ACLMessage(
        sender="BookingAPI",
        receiver="BookingAgent",
        performative=Performative.REQUEST,
        content={
            "action": "CREATE_BOOKING",
            "user_id": 1,
            "event_id": 1,
            "category_id": 1,
            "quantity": 0
        }
    )

    agent.receive_message(message)

    assert len(bus.sent_messages) == 1
    assert bus.sent_messages[0].performative == Performative.REFUSE
    assert "greater than zero" in bus.sent_messages[0].content["reason"]


def test_booking_agent_rejects_missing_fields():
    agent, bus = create_agent()

    message = ACLMessage(
        sender="BookingAPI",
        receiver="BookingAgent",
        performative=Performative.REQUEST,
        content={
            "action": "CREATE_BOOKING",
            "user_id": 1
        }
    )

    agent.receive_message(message)

    assert len(bus.sent_messages) == 1
    assert bus.sent_messages[0].performative == Performative.REFUSE


def test_booking_agent_rejects_non_request_message():
    agent, bus = create_agent()

    message = ACLMessage(
        sender="BookingAPI",
        receiver="BookingAgent",
        performative=Performative.INFORM,
        content={"action": "CREATE_BOOKING"}
    )

    agent.receive_message(message)

    assert len(bus.sent_messages) == 1
    assert bus.sent_messages[0].performative == Performative.REFUSE
