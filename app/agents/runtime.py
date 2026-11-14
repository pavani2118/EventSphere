
from app.agents import waitlist_agent
from app.agents import message_bus
from app.agents import venue_agent
from app.agents import booking_agent
from app.agents import ticket_agent
from app.agents.message_bus import MessageBus
from app.agents.venue_agent import VenueAgent
from app.agents.booking_agent import BookingAgent
from app.agents.ticket_agent import TicketAgent

from app.agents.waitlist_agent import WaitlistAgent
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

    ticket_agent = TicketAgent(
        name="TicketAgent",
        message_bus=message_bus
    )

    waitlist_agent = WaitlistAgent(
        name="WaitlistAgent",
        message_bus=message_bus
    )

    message_bus.register(venue_agent)
    message_bus.register(booking_agent)
    message_bus.register(ticket_agent)
    message_bus.register(waitlist_agent)
    
    return {
        "message_bus": message_bus,
        "venue_agent": venue_agent,
        "booking_agent": booking_agent,
        "ticket_agent": ticket_agent,
        "waitlist_agent": waitlist_agent
    }
