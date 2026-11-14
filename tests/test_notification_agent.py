
from app.agents.notification_agent import NotificationAgent
from app.agents.message import ACLMessage, Performative


class FakeMessageBus:
    def __init__(self):
        self.sent_messages = []

    def send(self, message):
        self.sent_messages.append(message)
        return message


def create_agent():
    bus = FakeMessageBus()
    agent = NotificationAgent("NotificationAgent", bus)
    return agent, bus


def create_message(action, content=None, performative=Performative.INFORM):
    return ACLMessage(
        sender="BookingAgent",
        receiver="NotificationAgent",
        performative=performative,
        content={"action": action, **(content or {})}
    )


def test_notification_agent_rejects_non_inform():
    agent, bus = create_agent()

    message = create_message(
        "SEND_NOTIFICATION",
        performative=Performative.REQUEST
    )

    response = agent.receive_message(message)

    assert response.performative == Performative.REFUSE


def test_notification_agent_rejects_unknown_action():
    agent, bus = create_agent()

    message = create_message("UNKNOWN_ACTION")
    response = agent.receive_message(message)

    assert response.performative == Performative.REFUSE


def test_notification_agent_rejects_invalid_user_id():
    agent, bus = create_agent()

    message = create_message(
        "SEND_NOTIFICATION",
        {"user_id": "invalid", "message": "Booking confirmed"}
    )

    response = agent.send_notification(message)

    assert response.performative == Performative.REFUSE


def test_notification_agent_rejects_zero_user_id():
    agent, bus = create_agent()

    message = create_message(
        "SEND_NOTIFICATION",
        {"user_id": 0, "message": "Booking confirmed"}
    )

    response = agent.send_notification(message)

    assert response.performative == Performative.REFUSE


def test_notification_agent_rejects_empty_message():
    agent, bus = create_agent()

    message = create_message(
        "SEND_NOTIFICATION",
        {"user_id": 1, "message": "   "}
    )

    response = agent.send_notification(message)

    assert response.performative == Performative.REFUSE


def test_notification_agent_rejects_missing_fields():
    agent, bus = create_agent()

    message = create_message("SEND_NOTIFICATION", {})

    response = agent.send_notification(message)

    assert response.performative == Performative.REFUSE


def test_notification_agent_rejects_message_over_1000_characters():
    agent, bus = create_agent()

    message = create_message(
        "SEND_NOTIFICATION",
        {"user_id": 1, "message": "A" * 1001}
    )

    response = agent.send_notification(message)

    assert response.performative == Performative.REFUSE


def test_notification_agent_accepts_inform_action():
    agent, bus = create_agent()

    # Avoid database access in this message-routing unit test.
    agent.send_notification = lambda message: agent._reply(
        message,
        Performative.AGREE,
        {"success": True}
    )

    message = create_message(
        "SEND_NOTIFICATION",
        {"user_id": 1, "message": "Booking confirmed"}
    )

    response = agent.receive_message(message)

    assert response.performative == Performative.AGREE
    assert response.content["success"] is True
