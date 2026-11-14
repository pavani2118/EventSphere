
from app.agents.booking_agent import BookingAgent
from app.agents.runtime import create_agent_runtime
from app.agents.venue_agent import VenueAgent


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
