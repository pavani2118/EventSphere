
from app.agents.venue_agent import VenueAgent
from app.agents.message import ACLMessage, Performative


class FakeMessageBus:
    def __init__(self):
        self.sent_messages = []

    def send(self, message):
        self.sent_messages.append(message)
        return message


def create_agent():
    bus = FakeMessageBus()
    agent = VenueAgent("VenueAgent", bus)
    return agent, bus


def test_venue_agent_rejects_unknown_action():
    agent, bus = create_agent()

    message = ACLMessage(
        sender="BookingAgent",
        receiver="VenueAgent",
        performative=Performative.REQUEST,
        content={"action": "UNKNOWN_ACTION"}
    )

    agent.receive_message(message)

    assert len(bus.sent_messages) == 1
    assert bus.sent_messages[0].performative == Performative.REFUSE
    assert "Unsupported action" in bus.sent_messages[0].content["reason"]


def test_venue_agent_rejects_invalid_datetime():
    agent, bus = create_agent()

    message = ACLMessage(
        sender="BookingAgent",
        receiver="VenueAgent",
        performative=Performative.REQUEST,
        content={
            "action": "CHECK_AVAILABILITY",
            "venue_id": 1,
            "start_time": "2026-12-01T10:00:00",
            "end_time": "2026-12-01T12:00:00"
        }
    )

    agent.receive_message(message)

    assert len(bus.sent_messages) == 1
    assert bus.sent_messages[0].performative == Performative.REFUSE
    assert "Timezone is required" in bus.sent_messages[0].content["reason"]
