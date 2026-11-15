
from app.agents.message import ACLMessage, Performative
from app.agents.message_bus import MessageBus
from app.agents.base_agent import BaseAgent


# A simple agent used only for testing.
class DummyAgent:

    def __init__(self, name):
        self.name = name
        self.received_messages = []

    def receive_message(self, message):
        self.received_messages.append(message)

        return {
            "status": "received",
            "agent": self.name
        }


# Agent used to test PostgreSQL state persistence.
class StateTestAgent(BaseAgent):

    def receive_message(self, message):
        return {"status": "received"}


def test_acl_message_creation():

    message = ACLMessage(
        sender="BookingAgent",
        receiver="VenueAgent",
        performative=Performative.REQUEST,
        content={
            "action": "CHECK_AVAILABILITY",
            "venue_id": 1
        }
    )

    assert message.sender == "BookingAgent"
    assert message.receiver == "VenueAgent"
    assert message.performative == Performative.REQUEST
    assert message.content["venue_id"] == 1
    assert message.conversation_id


def test_message_bus_registration():

    bus = MessageBus()
    agent = DummyAgent("VenueAgent")

    bus.register(agent)

    assert "VenueAgent" in bus.agents


def test_message_bus_rejects_duplicate_agent():

    bus = MessageBus()

    bus.register(DummyAgent("VenueAgent"))

    try:
        bus.register(DummyAgent("VenueAgent"))
        assert False, "Duplicate registration should fail"

    except ValueError:
        assert True


def test_message_bus_rejects_unknown_receiver():

    bus = MessageBus()

    message = ACLMessage(
        sender="BookingAgent",
        receiver="UnknownAgent",
        performative=Performative.REQUEST,
        content={}
    )

    # Avoid PostgreSQL logging in this isolated routing test.
    bus.log_message = lambda message: None

    try:
        bus.send(message)
        assert False, "Unknown receiver should fail"

    except ValueError as error:
        assert "Receiver agent not found" in str(error)


def test_base_agent_returns_receiver_response():
    bus = MessageBus()
    receiver = DummyAgent("VenueAgent")
    bus.register(receiver)
    bus.log_message = lambda message: None

    sender = StateTestAgent("BookingAgent", bus)
    response = sender.send_message(
        receiver="VenueAgent",
        performative=Performative.REQUEST,
        content={"action": "CHECK_AVAILABILITY"}
    )

    assert response["status"] == "received"
    assert response["agent"] == "VenueAgent"


def test_message_bus_returns_failure_when_receiver_raises():
    class FailingAgent:
        name = "VenueAgent"

        def receive_message(self, message):
            raise RuntimeError("database unavailable")

    bus = MessageBus()
    bus.register(FailingAgent())
    bus.log_message = lambda message: None

    response = bus.send(
        ACLMessage(
            sender="BookingAPI",
            receiver="VenueAgent",
            performative=Performative.REQUEST
        )
    )

    assert response.performative == Performative.FAILURE
    assert response.receiver == "BookingAPI"
    assert "could not process" in response.content["reason"]


def test_agent_state_persistence():

    bus = MessageBus()

    agent = StateTestAgent(
        "StateTestAgent",
        bus
    )

    agent.state = {
        "tasks_completed": 5,
        "status": "ACTIVE"
    }

    agent.save_state()

    new_agent = StateTestAgent(
        "StateTestAgent",
        bus
    )

    loaded_state = new_agent.load_state()

    assert loaded_state["tasks_completed"] == 5
    assert loaded_state["status"] == "ACTIVE"
