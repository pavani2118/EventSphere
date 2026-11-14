
from app.agents.message_bus import MessageBus

from app.agents.venue_agent import VenueAgent
from app.agents.booking_agent import BookingAgent
from app.agents.ticket_agent import TicketAgent
from app.agents.waitlist_agent import WaitlistAgent
from app.agents.notification_agent import NotificationAgent
from app.agents.api_gateway import APIGatewayAgent


def create_agent_runtime():

    # Create one message bus.
    message_bus = MessageBus()

    # Create all five agents.
    venue_agent = VenueAgent(
        "VenueAgent",
        message_bus
    )

    booking_agent = BookingAgent(
        "BookingAgent",
        message_bus
    )

    ticket_agent = TicketAgent(
        "TicketAgent",
        message_bus
    )

    waitlist_agent = WaitlistAgent(
        "WaitlistAgent",
        message_bus
    )

    notification_agent = NotificationAgent(
        "NotificationAgent",
        message_bus
    )

    # Create separate API gateways.
    booking_api_gateway = APIGatewayAgent("BookingAPI")

    ticket_api_gateway = APIGatewayAgent("TicketAPI")

    # Register each agent exactly once.
    message_bus.register(venue_agent)
    message_bus.register(booking_agent)
    message_bus.register(ticket_agent)
    message_bus.register(waitlist_agent)
    message_bus.register(notification_agent)

    # Register each gateway exactly once.
    message_bus.register(booking_api_gateway)
    message_bus.register(ticket_api_gateway)

    return {
        "message_bus": message_bus,

        "venue_agent": venue_agent,
        "booking_agent": booking_agent,
        "ticket_agent": ticket_agent,
        "waitlist_agent": waitlist_agent,
        "notification_agent": notification_agent,

        "api_gateway": booking_api_gateway,
        "booking_api_gateway": booking_api_gateway,
        "ticket_api_gateway": ticket_api_gateway
    }
