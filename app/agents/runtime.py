
from app.agents.message_bus import MessageBus
from app.agents.venue_agent import VenueAgent
from app.agents.booking_agent import BookingAgent


def create_agent_runtime():
    """
    Creates one shared MessageBus and registers all implemented agents.
    """

    message_bus = MessageBus()

    venue_agent = VenueAgent(
        name="VenueAgent",
        message_bus=message_bus
    )

    booking_agent = BookingAgent(
        name="BookingAgent",
        message_bus=message_bus
    )

    message_bus.register(venue_agent)
    message_bus.register(booking_agent)

    return {
        "message_bus": message_bus,
        "venue_agent": venue_agent,
        "booking_agent": booking_agent
    }
