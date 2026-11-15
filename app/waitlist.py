
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.database import get_db_connection
from app.dependencies import require_roles
from app.agents.message import ACLMessage, Performative


router = APIRouter(
    prefix="/waitlist",
    tags=["Waitlist Management"]
)


class WaitlistJoinRequest(BaseModel):
    event_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=10)


def send_waitlist_message(request, action, content):

    runtime = getattr(request.app.state, "agent_runtime", None)

    if runtime is None:
        raise HTTPException(
            status_code=503,
            detail="Agent system is not available."
        )

    message = ACLMessage(
        sender="WaitlistAPI",
        receiver="WaitlistAgent",
        performative=Performative.REQUEST,
        content={
            "action": action,
            **content
        }
    )

    response = runtime["message_bus"].send(message)

    if response.performative == Performative.REFUSE:
        raise HTTPException(
            status_code=400,
            detail=response.content.get(
                "reason",
                "Waitlist request was rejected."
            )
        )

    if response.performative != Performative.AGREE:
        raise HTTPException(
            status_code=500,
            detail=response.content.get(
                "reason",
                "Waitlist operation failed."
            )
        )

    return response.content


# Join the waitlist
@router.post("/join", status_code=201)
def join_waitlist(
    data: WaitlistJoinRequest,
    request: Request,
    current_user=Depends(require_roles("ATTENDEE"))
):

    return send_waitlist_message(
        request,
        "JOIN_WAITLIST",
        {
            "user_id": current_user["id"],
            "event_id": data.event_id,
            "quantity": data.quantity
        }
    )


# View my waitlist entries
@router.get("/my-waitlist")
def get_my_waitlist(
    current_user=Depends(require_roles("ATTENDEE"))
):

    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    w.id AS waitlist_id,
                    w.event_id,
                    e.title AS event_title,
                    w.quantity,
                    w.status,
                    w.created_at
                FROM waitlist w
                JOIN events e ON e.id = w.event_id
                WHERE w.user_id = %s
                ORDER BY w.created_at DESC, w.id DESC
                """,
                (current_user["id"],)
            )

            entries = cursor.fetchall()

    return {
        "total_entries": len(entries),
        "waitlist": entries
    }


# Admin manually processes an event waitlist
@router.post("/process/{event_id}")
def process_event_waitlist(
    event_id: int,
    request: Request,
    current_user=Depends(require_roles("ADMIN"))
):

    return send_waitlist_message(
        request,
        "PROCESS_WAITLIST",
        {"event_id": event_id}
    )
