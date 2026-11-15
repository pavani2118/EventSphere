
from app.agents.waitlist_agent import WaitlistAgent
from app.agents.message import ACLMessage, Performative


class FakeMessageBus:
    def __init__(self):
        self.sent_messages = []

    def send(self, message):
        self.sent_messages.append(message)
        return message


def create_agent():
    bus = FakeMessageBus()
    agent = WaitlistAgent("WaitlistAgent", bus)
    return agent, bus


def create_message(action, content=None, performative=Performative.REQUEST):
    return ACLMessage(
        sender="BookingAgent",
        receiver="WaitlistAgent",
        performative=performative,
        content={"action": action, **(content or {})}
    )


def test_unknown_action_is_refused():
    agent, bus = create_agent()

    message = create_message("UNKNOWN_ACTION")
    response = agent.receive_message(message)

    assert response.performative == Performative.REFUSE


def test_response_message_is_returned_without_rerouting():
    agent, bus = create_agent()

    message = create_message(
        "JOIN_WAITLIST",
        performative=Performative.AGREE
    )
    response = agent.receive_message(message)

    assert response is message
    assert bus.sent_messages == []


def test_join_waitlist_rejects_missing_fields():
    agent, bus = create_agent()

    message = create_message("JOIN_WAITLIST", {})
    response = agent.receive_message(message)

    assert response.performative == Performative.REFUSE


def test_join_waitlist_rejects_invalid_quantity():
    agent, bus = create_agent()

    message = create_message(
        "JOIN_WAITLIST",
        {"user_id": 1, "event_id": 1, "quantity": 0}
    )
    response = agent.receive_message(message)

    assert response.performative == Performative.REFUSE


def test_join_waitlist_rejects_quantity_over_ten():
    agent, bus = create_agent()

    message = create_message(
        "JOIN_WAITLIST",
        {"user_id": 1, "event_id": 1, "quantity": 11}
    )
    response = agent.receive_message(message)

    assert response.performative == Performative.REFUSE


def test_process_waitlist_rejects_invalid_event_id():
    agent, bus = create_agent()

    message = create_message(
        "PROCESS_WAITLIST",
        {"event_id": "invalid"}
    )
    response = agent.receive_message(message)

    assert response.performative == Performative.REFUSE


def test_expire_waitlist_action_is_recognised():
    agent, bus = create_agent()

    # Replace database-dependent method with a test response.
    agent.expire_waitlist = lambda message: agent._reply(
        message,
        Performative.AGREE,
        {"success": True, "expired_count": 0}
    )

    message = create_message("EXPIRE_WAITLIST")
    response = agent.receive_message(message)

    assert response.performative == Performative.AGREE
