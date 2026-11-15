
from app.agents.booking_agent import BookingAgent
from app.agents.runtime import create_agent_runtime
from app.agents.venue_agent import VenueAgent
from app.agents.waitlist_agent import WaitlistAgent
from app.agents.ticket_agent import TicketAgent
from app.agents.notification_agent import NotificationAgent
from app.agents.api_gateway import APIGatewayAgent
def test_runtime_creates_message_bus():
    runtime = create_agent_runtime()

    assert runtime["message_bus"] is not None


def test_runtime_registers_venue_agent():
    runtime = create_agent_runtime()

    assert "VenueAgent" in runtime["message_bus"].agents
    assert isinstance(
        runtime["message_bus"].agents["VenueAgent"],
        VenueAgent
    )

def test_runtime_registers_notification_agent():
    runtime = create_agent_runtime()

    assert "NotificationAgent" in runtime["message_bus"].agents

    assert isinstance(
        runtime["message_bus"].agents["NotificationAgent"],
        NotificationAgent
    )
def test_runtime_returns_registered_agent():
    runtime = create_agent_runtime()

    assert runtime["venue_agent"] is (
        runtime["message_bus"].agents["VenueAgent"]
    )

def test_runtime_registers_booking_agent():
    runtime = create_agent_runtime()

    assert "BookingAgent" in runtime["message_bus"].agents
    assert isinstance(
        runtime["message_bus"].agents["BookingAgent"],
        BookingAgent
    )

def test_runtime_registers_ticket_agent():
    runtime = create_agent_runtime()

    assert "TicketAgent" in runtime["message_bus"].agents
    assert isinstance(
        runtime["message_bus"].agents["TicketAgent"],
        TicketAgent
    )

def test_runtime_registers_waitlist_agent():
    runtime = create_agent_runtime()

    assert "WaitlistAgent" in runtime["message_bus"].agents

    assert isinstance(
        runtime["message_bus"].agents["WaitlistAgent"],
        WaitlistAgent
    )

def test_runtime_registers_api_gateway():
    runtime = create_agent_runtime()

    assert "BookingAPI" in runtime["message_bus"].agents

    assert isinstance(
        runtime["message_bus"].agents["BookingAPI"],
        APIGatewayAgent
    )


def test_runtime_does_not_restore_state_by_default(monkeypatch):
    runtime = create_agent_runtime()
    assert runtime["booking_agent"].state == {}