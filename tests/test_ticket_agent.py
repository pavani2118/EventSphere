
from app.agents.ticket_agent import TicketAgent
from app.agents.message import ACLMessage, Performative


class FakeMessageBus:
    def __init__(self):
        self.sent_messages = []

    def send(self, message):
        self.sent_messages.append(message)
        return message


def create_agent():
    bus = FakeMessageBus()
    agent = TicketAgent("TicketAgent", bus)
    return agent, bus


def test_ticket_agent_rejects_unknown_action():
    agent, bus = create_agent()

    message = ACLMessage(
        sender="GateStaffAgent",
        receiver="TicketAgent",
        performative=Performative.REQUEST,
        content={"action": "UNKNOWN_ACTION"}
    )

    agent.receive_message(message)

    assert len(bus.sent_messages) == 1
    assert bus.sent_messages[0].performative == Performative.REFUSE
    assert "Unsupported action" in bus.sent_messages[0].content["reason"]


def test_ticket_agent_rejects_non_request_message():
    agent, bus = create_agent()

    message = ACLMessage(
        sender="GateStaffAgent",
        receiver="TicketAgent",
        performative=Performative.INFORM,
        content={"action": "CHECK_IN"}
    )

    agent.receive_message(message)

    assert len(bus.sent_messages) == 1
    assert bus.sent_messages[0].performative == Performative.REFUSE


def test_ticket_agent_rejects_missing_qr_token():
    agent, bus = create_agent()

    message = ACLMessage(
        sender="GateStaffAgent",
        receiver="TicketAgent",
        performative=Performative.REQUEST,
        content={
            "action": "CHECK_IN",
            "staff_user_id": 1
        }
    )

    agent.receive_message(message)

    assert len(bus.sent_messages) == 1
    assert bus.sent_messages[0].performative == Performative.REFUSE
    assert "QR token" in bus.sent_messages[0].content["reason"]


def test_ticket_agent_rejects_short_qr_token():
    agent, bus = create_agent()

    message = ACLMessage(
        sender="GateStaffAgent",
        receiver="TicketAgent",
        performative=Performative.REQUEST,
        content={
            "action": "CHECK_IN",
            "qr_token": "short-token",
            "staff_user_id": 1
        }
    )

    agent.receive_message(message)

    assert len(bus.sent_messages) == 1
    assert bus.sent_messages[0].performative == Performative.REFUSE
    assert "Invalid QR token length" in bus.sent_messages[0].content["reason"]


def test_ticket_agent_rejects_invalid_staff_id():
    agent, bus = create_agent()

    message = ACLMessage(
        sender="GateStaffAgent",
        receiver="TicketAgent",
        performative=Performative.REQUEST,
        content={
            "action": "CHECK_IN",
            "qr_token": "A" * 32,
            "staff_user_id": "invalid"
        }
    )

    agent.receive_message(message)

    assert len(bus.sent_messages) == 1
    assert bus.sent_messages[0].performative == Performative.REFUSE
    assert "staff user ID" in bus.sent_messages[0].content["reason"]


def test_ticket_agent_rejects_zero_staff_id():
    agent, bus = create_agent()

    message = ACLMessage(
        sender="GateStaffAgent",
        receiver="TicketAgent",
        performative=Performative.REQUEST,
        content={
            "action": "CHECK_IN",
            "qr_token": "A" * 32,
            "staff_user_id": 0
        }
    )

    agent.receive_message(message)

    assert len(bus.sent_messages) == 1
    assert bus.sent_messages[0].performative == Performative.REFUSE
    assert "Invalid staff user ID" in bus.sent_messages[0].content["reason"]
