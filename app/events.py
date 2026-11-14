
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db_connection
from app.dependencies import require_roles
from app.event_schemas import EventCreate, EventUpdate
from app.ticket_schemas import TicketCategoriesCreate


router = APIRouter(
    prefix="/events",
    tags=["Event Management"]
)


# Venue turnaround buffer: 60 minutes
TURNAROUND_BUFFER_MINUTES = 60


# --------------------------------------------------
# CREATE EVENT
# --------------------------------------------------

@router.post("/", status_code=201)
def create_event(
    event: EventCreate,
    current_user=Depends(require_roles("ADMIN", "ORGANISER"))
):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            # Lock venue to prevent simultaneous booking conflicts
            cursor.execute(
                """
                SELECT id, capacity
                FROM venues
                WHERE id = %s
                FOR UPDATE
                """,
                (event.venue_id,)
            )

            venue = cursor.fetchone()

            if venue is None:
                raise HTTPException(
                    status_code=404,
                    detail="Venue not found"
                )

            # Check venue time conflicts
            buffer = timedelta(
                minutes=TURNAROUND_BUFFER_MINUTES
            )

            cursor.execute(
                """
                SELECT id, title
                FROM events
                WHERE venue_id = %s
                  AND status != 'CANCELLED'
                  AND start_time < %s
                  AND end_time > %s
                LIMIT 1
                """,
                (
                    event.venue_id,
                    event.end_time + buffer,
                    event.start_time - buffer
                )
            )

            conflict = cursor.fetchone()

            if conflict:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "Venue is already booked during this time",
                        "conflicting_event": conflict["title"]
                    }
                )

            # Create event as DRAFT
            cursor.execute(
                """
                INSERT INTO events (
                    title,
                    category,
                    venue_id,
                    start_time,
                    end_time,
                    description,
                    status,
                    created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'DRAFT', %s)
                RETURNING *
                """,
                (
                    event.title,
                    event.category,
                    event.venue_id,
                    event.start_time,
                    event.end_time,
                    event.description,
                    current_user["id"]
                )
            )

            new_event = cursor.fetchone()

    return {
        "message": "Event created successfully",
        "event": new_event
    }


# --------------------------------------------------
# VIEW ALL PUBLISHED EVENTS
# --------------------------------------------------

@router.get("/")
def get_all_events(
    category: str | None = None,
    venue_id: int | None = None
):
    query = """
        SELECT
            e.*,
            v.name AS venue_name,
            v.location AS venue_location
        FROM events e
        JOIN venues v ON e.venue_id = v.id
        WHERE e.status = 'PUBLISHED'
    """

    params = []

    if category:
        query += " AND LOWER(e.category) = LOWER(%s)"
        params.append(category)

    if venue_id:
        query += " AND e.venue_id = %s"
        params.append(venue_id)

    query += " ORDER BY e.start_time ASC"

    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(query, params)

            events = cursor.fetchall()

    return {
        "total": len(events),
        "events": events
    }


# --------------------------------------------------
# VIEW SINGLE PUBLISHED EVENT
# --------------------------------------------------

@router.get("/{event_id}")
def get_event(event_id: int):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    e.*,
                    v.name AS venue_name,
                    v.location AS venue_location
                FROM events e
                JOIN venues v ON e.venue_id = v.id
                WHERE e.id = %s
                  AND e.status = 'PUBLISHED'
                """,
                (event_id,)
            )

            event = cursor.fetchone()

            if event is None:
                raise HTTPException(
                    status_code=404,
                    detail="Published event not found"
                )

    return event


# --------------------------------------------------
# CREATE TICKET CATEGORIES
# --------------------------------------------------

@router.post(
    "/{event_id}/ticket-categories",
    status_code=201
)
def create_ticket_categories(
    event_id: int,
    data: TicketCategoriesCreate,
    current_user=Depends(
        require_roles("ADMIN", "ORGANISER")
    )
):
    # Check duplicate category names
    category_names = [
        category.category_name.strip().lower()
        for category in data.categories
    ]

    if len(category_names) != len(set(category_names)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate ticket category names are not allowed"
        )

    # Calculate total ticket quantity
    total_quantity = sum(
        category.quantity
        for category in data.categories
    )

    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            # Find and lock event
            cursor.execute(
                """
                SELECT id, venue_id, status, created_by
                FROM events
                WHERE id = %s
                FOR UPDATE
                """,
                (event_id,)
            )

            event = cursor.fetchone()

            if event is None:
                raise HTTPException(
                    status_code=404,
                    detail="Event not found"
                )

            # Check event ownership
            if (
                current_user["role"] != "ADMIN"
                and event["created_by"] != current_user["id"]
            ):
                raise HTTPException(
                    status_code=403,
                    detail="You cannot manage this event"
                )

            # Only draft events can receive categories
            if event["status"] != "DRAFT":
                raise HTTPException(
                    status_code=400,
                    detail="Ticket categories can only be added to draft events"
                )

            # Lock venue and get capacity
            cursor.execute(
                """
                SELECT id, capacity
                FROM venues
                WHERE id = %s
                FOR UPDATE
                """,
                (event["venue_id"],)
            )

            venue = cursor.fetchone()

            if venue is None:
                raise HTTPException(
                    status_code=404,
                    detail="Venue not found"
                )

            # Validate venue capacity
            if total_quantity > venue["capacity"]:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Total ticket quantity exceeds venue capacity",
                        "venue_capacity": venue["capacity"],
                        "requested_tickets": total_quantity
                    }
                )

            # Check existing categories
            cursor.execute(
                """
                SELECT COUNT(*) AS category_count
                FROM ticket_categories
                WHERE event_id = %s
                """,
                (event_id,)
            )

            existing = cursor.fetchone()

            if existing["category_count"] > 0:
                raise HTTPException(
                    status_code=409,
                    detail="Ticket categories already exist for this event"
                )

            # Insert ticket categories
            created_categories = []

            for category in data.categories:
                cursor.execute(
                    """
                    INSERT INTO ticket_categories (
                        event_id,
                        category_name,
                        price,
                        quantity
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        event_id,
                        category.category_name.strip(),
                        category.price,
                        category.quantity
                    )
                )

                created_categories.append(
                    cursor.fetchone()
                )

    return {
        "message": "Ticket categories created successfully",
        "event_id": event_id,
        "total_ticket_quantity": total_quantity,
        "venue_capacity": venue["capacity"],
        "categories": created_categories
    }


# --------------------------------------------------
# UPDATE DRAFT EVENT
# --------------------------------------------------

@router.put("/{event_id}")
def update_event(
    event_id: int,
    event: EventUpdate,
    current_user=Depends(
        require_roles("ADMIN", "ORGANISER")
    )
):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            # Find and lock event
            cursor.execute(
                """
                SELECT id, status, created_by
                FROM events
                WHERE id = %s
                FOR UPDATE
                """,
                (event_id,)
            )

            existing_event = cursor.fetchone()

            if existing_event is None:
                raise HTTPException(
                    status_code=404,
                    detail="Event not found"
                )

            # Check ownership
            if (
                current_user["role"] != "ADMIN"
                and existing_event["created_by"] != current_user["id"]
            ):
                raise HTTPException(
                    status_code=403,
                    detail="You cannot manage this event"
                )

            # Only draft events can be updated
            if existing_event["status"] != "DRAFT":
                raise HTTPException(
                    status_code=400,
                    detail="Only draft events can be updated"
                )

            # Lock the selected venue
            cursor.execute(
                """
                SELECT id
                FROM venues
                WHERE id = %s
                FOR UPDATE
                """,
                (event.venue_id,)
            )

            venue = cursor.fetchone()

            if venue is None:
                raise HTTPException(
                    status_code=404,
                    detail="Venue not found"
                )

            # Check venue time conflicts
            buffer = timedelta(
                minutes=TURNAROUND_BUFFER_MINUTES
            )

            cursor.execute(
                """
                SELECT id, title
                FROM events
                WHERE venue_id = %s
                  AND id != %s
                  AND status != 'CANCELLED'
                  AND start_time < %s
                  AND end_time > %s
                LIMIT 1
                """,
                (
                    event.venue_id,
                    event_id,
                    event.end_time + buffer,
                    event.start_time - buffer
                )
            )

            conflict = cursor.fetchone()

            if conflict:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "Venue is already booked during this time",
                        "conflicting_event": conflict["title"]
                    }
                )

            # Update event
            cursor.execute(
                """
                UPDATE events
                SET title = %s,
                    category = %s,
                    venue_id = %s,
                    start_time = %s,
                    end_time = %s,
                    description = %s
                WHERE id = %s
                RETURNING *
                """,
                (
                    event.title,
                    event.category,
                    event.venue_id,
                    event.start_time,
                    event.end_time,
                    event.description,
                    event_id
                )
            )

            updated_event = cursor.fetchone()

    return {
        "message": "Event updated successfully",
        "event": updated_event
    }


# --------------------------------------------------
# PUBLISH EVENT
# --------------------------------------------------

@router.post("/{event_id}/publish")
def publish_event(
    event_id: int,
    current_user=Depends(
        require_roles("ADMIN", "ORGANISER")
    )
):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            # Find and lock event
            cursor.execute(
                """
                SELECT id, status, created_by
                FROM events
                WHERE id = %s
                FOR UPDATE
                """,
                (event_id,)
            )

            event = cursor.fetchone()

            if event is None:
                raise HTTPException(
                    status_code=404,
                    detail="Event not found"
                )

            # Check ownership
            if (
                current_user["role"] != "ADMIN"
                and event["created_by"] != current_user["id"]
            ):
                raise HTTPException(
                    status_code=403,
                    detail="You cannot manage this event"
                )

            if event["status"] != "DRAFT":
                raise HTTPException(
                    status_code=400,
                    detail="Only draft events can be published"
                )

            # Check ticket categories
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS category_count,
                    COALESCE(SUM(quantity), 0) AS total_quantity
                FROM ticket_categories
                WHERE event_id = %s
                """,
                (event_id,)
            )

            category_info = cursor.fetchone()

            if category_info["category_count"] == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Add at least one ticket category before publishing"
                )

            # Check total ticket quantity against venue capacity
            cursor.execute(
                """
                SELECT v.capacity
                FROM events e
                JOIN venues v ON e.venue_id = v.id
                WHERE e.id = %s
                """,
                (event_id,)
            )

            venue = cursor.fetchone()

            if venue is None:
                raise HTTPException(
                    status_code=404,
                    detail="Venue not found"
                )

            if category_info["total_quantity"] > venue["capacity"]:
                raise HTTPException(
                    status_code=400,
                    detail="Ticket quantity exceeds venue capacity"
                )

            # Publish event
            cursor.execute(
                """
                UPDATE events
                SET status = 'PUBLISHED'
                WHERE id = %s
                RETURNING *
                """,
                (event_id,)
            )

            published_event = cursor.fetchone()

    return {
        "message": "Event published successfully",
        "event": published_event
    }


# --------------------------------------------------
# CANCEL EVENT
# --------------------------------------------------

@router.post("/{event_id}/cancel")
def cancel_event(
    event_id: int,
    current_user=Depends(
        require_roles("ADMIN", "ORGANISER")
    )
):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            # Find and lock event
            cursor.execute(
                """
                SELECT id, status, created_by
                FROM events
                WHERE id = %s
                FOR UPDATE
                """,
                (event_id,)
            )

            event = cursor.fetchone()

            if event is None:
                raise HTTPException(
                    status_code=404,
                    detail="Event not found"
                )

            # Check ownership
            if (
                current_user["role"] != "ADMIN"
                and event["created_by"] != current_user["id"]
            ):
                raise HTTPException(
                    status_code=403,
                    detail="You cannot manage this event"
                )

            if event["status"] == "CANCELLED":
                raise HTTPException(
                    status_code=400,
                    detail="Event is already cancelled"
                )

            # Cancel event
            cursor.execute(
                """
                UPDATE events
                SET status = 'CANCELLED'
                WHERE id = %s
                RETURNING *
                """,
                (event_id,)
            )

            cancelled_event = cursor.fetchone()

    return {
        "message": "Event cancelled successfully",
        "event": cancelled_event
    }
