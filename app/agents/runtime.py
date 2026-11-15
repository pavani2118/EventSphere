
from app.agents.message_bus import MessageBus

from app.agents.venue_agent import VenueAgent
from app.agents.booking_agent import BookingAgent
from app.agents.ticket_agent import TicketAgent
from app.agents.waitlist_agent import WaitlistAgent
from app.agents.notification_agent import NotificationAgent
from app.agents.api_gateway import APIGatewayAgent
import logging


logger = logging.getLogger(__name__)


def create_agent_runtime(load_persisted_state=False):

    # Create message bus
    message_bus = MessageBus()

    # ----------------------------------------
    # CREATE FIVE AGENTS
    # ----------------------------------------

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

    # ----------------------------------------
    # CREATE API GATEWAYS
    # ----------------------------------------

    booking_api_gateway = APIGatewayAgent("BookingAPI")

    ticket_api_gateway = APIGatewayAgent("TicketAPI")

    venue_hire_api_gateway = APIGatewayAgent("VenueHireAPI")

    waitlist_scheduler_gateway = APIGatewayAgent(
        "WaitlistScheduler"
    )

    waitlist_api_gateway = APIGatewayAgent(
        "WaitlistAPI"
    )

    # ----------------------------------------
    # REGISTER FIVE AGENTS
    # ----------------------------------------

    message_bus.register(venue_agent)

    message_bus.register(booking_agent)

    message_bus.register(ticket_agent)

    message_bus.register(waitlist_agent)

    message_bus.register(notification_agent)

    # ----------------------------------------
    # REGISTER API GATEWAYS
    # ----------------------------------------

    message_bus.register(booking_api_gateway)

    message_bus.register(ticket_api_gateway)

    message_bus.register(venue_hire_api_gateway)

    message_bus.register(waitlist_scheduler_gateway)
    message_bus.register(waitlist_api_gateway)

    if load_persisted_state:
        for agent in (
            venue_agent,
            booking_agent,
            ticket_agent,
            waitlist_agent,
            notification_agent
        ):
            try:
                agent.load_state()
            except Exception:
                logger.exception(
                    "Could not restore state for agent %s.",
                    agent.name
                )

    # ----------------------------------------
    # RETURN AGENT RUNTIME
    # ----------------------------------------

    return {
        "message_bus": message_bus,

        # Agents
        "venue_agent": venue_agent,
        "booking_agent": booking_agent,
        "ticket_agent": ticket_agent,
        "waitlist_agent": waitlist_agent,
        "notification_agent": notification_agent,

        # API Gateways
        "api_gateway": booking_api_gateway,
        "booking_api_gateway": booking_api_gateway,
        "ticket_api_gateway": ticket_api_gateway,
        "venue_hire_api_gateway": venue_hire_api_gateway,
        "waitlist_scheduler_gateway": waitlist_scheduler_gateway,
        "waitlist_api_gateway": waitlist_api_gateway
    }
