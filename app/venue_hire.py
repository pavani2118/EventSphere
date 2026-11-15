from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies import get_current_user
from app.database import get_db_connection
from app.agents.message import ACLMessage, Performative
from app.venue_hire_schemas import VenueHireRequest


router = APIRouter(
    prefix="/venue-hire",
    tags=["Private Venue Hire"]
)


def get_user_id(current_user):
    if isinstance(current_user, dict):
        return current_user["id"]

    return current_user.id


def send_venue_request(request: Request, content: dict):

    runtime = getattr(
        request.app.state,
        "agent_runtime",
        None
    )

    if runtime is None:
        raise HTTPException(
            status_code=503,
            detail="Agent runtime is not available."
        )

    message_bus = runtime["message_bus"]

    acl_message = ACLMessage(
        sender="VenueHireAPI",
        receiver="VenueAgent",
        performative=Performative.REQUEST,
        content=content
    )

    try:
        response = message_bus.send(acl_message)

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to communicate with VenueAgent."
        )

    if response is None:
        raise HTTPException(
            status_code=502,
            detail="VenueAgent did not return a response."
        )

    return {
        "performative": response.performative.value,
        **response.content
    }


@router.post("/availability")
def check_venue_availability(
    payload: VenueHireRequest,
    request: Request,
    current_user=Depends(get_current_user)
):

    content = payload.model_dump(mode="json")

    return send_venue_request(
        request,
        {
            "action": "CHECK_AVAILABILITY",
            **content
        }
    )


@router.post("/request")
def create_venue_hire_request(
    payload: VenueHireRequest,
    request: Request,
    current_user=Depends(get_current_user)
):

    content = payload.model_dump(mode="json")

    content["user_id"] = get_user_id(current_user)

    return send_venue_request(
        request,
        {
            "action": "REQUEST_PRIVATE_HIRE",
            **content
        }
    )


@router.get("/my-requests")
def get_my_venue_hire_requests(current_user=Depends(get_current_user)):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.id AS request_id,
                       r.venue_id,
                       v.name AS venue_name,
                       r.start_time,
                       r.end_time,
                       r.guest_count,
                       r.quoted_price,
                       r.status,
                       r.created_at
                FROM venue_hire_requests r
                JOIN venues v ON v.id = r.venue_id
                WHERE r.user_id = %s
                ORDER BY r.created_at DESC, r.id DESC
                """,
                (get_user_id(current_user),)
            )
            requests = cursor.fetchall()

    return {
        "total_requests": len(requests),
        "requests": requests
    }