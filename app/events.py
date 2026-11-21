
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
                raise HTTPException(status_code=404, detail="Venue not found")

            buffer = timedelta(minutes=TURNAROUND_BUFFER_MINUTES)

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

            cursor.execute(
                """
                INSERT INTO events (
                    title, category, venue_id, start_time,
                    end_time, description, status, created_by
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
# VIEW ALL PUBLISHED EVENTS (PUBLIC)
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
# VIEW ALL EVENTS FOR ADMIN / ORGANISER
# Includes DRAFT, PUBLISHED and CANCELLED
# --------------------------------------------------

@router.get("/manage/all")
def get_all_events_for_management(
    current_user=Depends(require_roles("ADMIN", "ORGANISER"))
):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    e.*,
                    v.name AS venue_name,
                    v.location AS venue_location
                FROM events e
                LEFT JOIN venues v ON e.venue_id = v.id
                WHERE %s = 'ADMIN' OR e.created_by = %s
                ORDER BY e.created_at DESC
                """,
                (
                    current_user["role"],
                    current_user["id"]
                )
            )

            events = cursor.fetchall()

    return {
        "total": len(events),
        "events": events
    }

@router.get("/manage/{event_id}/ticket-categories")
def get_management_ticket_categories(
    event_id: int,
    current_user=Depends(require_roles("ADMIN", "ORGANISER"))
):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT e.id, e.title, e.status, e.created_by,
                       v.capacity AS venue_capacity
                FROM events e
                JOIN venues v ON v.id = e.venue_id
                WHERE e.id = %s
            """, (event_id,))

            event = cursor.fetchone()

            if event is None:
                raise HTTPException(status_code=404, detail="Event not found")

            if (
                current_user["role"] != "ADMIN"
                and event["created_by"] != current_user["id"]
            ):
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to manage this event"
                )

            cursor.execute("""
                SELECT
                    tc.id,
                    tc.event_id,
                    tc.category_name,
                    tc.price,
                    tc.quantity,
                    COALESCE(s.sold_count, 0) AS sold_count,
                    GREATEST(
                        tc.quantity - COALESCE(s.sold_count, 0), 0
                    ) AS available_quantity
                FROM ticket_categories tc
                LEFT JOIN (
                    SELECT category_id, COUNT(*) AS sold_count
                    FROM tickets
                    WHERE status IN ('VALID', 'USED')
                    GROUP BY category_id
                ) s ON s.category_id = tc.id
                WHERE tc.event_id = %s
                ORDER BY tc.id
            """, (event_id,))

            categories = cursor.fetchall()

    return {
        "event": event,
        "categories": categories,
        "total_categories": len(categories)
    }


@router.post("/{event_id}/ticket-categories")
def add_ticket_categories(
    event_id: int,
    data: TicketCategoriesCreate,
    current_user=Depends(require_roles("ADMIN", "ORGANISER"))
):
    if not data.categories:
        raise HTTPException(
            status_code=400,
            detail="Please add at least one ticket category"
        )

    # Check duplicate names inside the submitted request
    submitted_names = [
        item.category_name.strip().casefold()
        for item in data.categories
    ]

    if len(submitted_names) != len(set(submitted_names)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate category names are not allowed"
        )

    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            # Lock the event while checking and adding categories
            cursor.execute("""
                SELECT e.id, e.title, e.status, e.created_by,
                       v.capacity AS venue_capacity
                FROM events e
                JOIN venues v ON v.id = e.venue_id
                WHERE e.id = %s
                FOR UPDATE OF e
            """, (event_id,))

            event = cursor.fetchone()

            if event is None:
                raise HTTPException(
                    status_code=404,
                    detail="Event not found"
                )

            if (
                current_user["role"] != "ADMIN"
                and event["created_by"] != current_user["id"]
            ):
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to manage this event"
                )

            if event["status"] != "DRAFT":
                raise HTTPException(
                    status_code=400,
                    detail="Ticket categories can only be added to draft events"
                )

            # Read existing categories
            cursor.execute("""
                SELECT category_name, quantity
                FROM ticket_categories
                WHERE event_id = %s
            """, (event_id,))

            existing_categories = cursor.fetchall()

            existing_names = {
                item["category_name"].strip().casefold()
                for item in existing_categories
            }

            # Prevent duplicate names with previously saved categories
            duplicate_names = [
                item.category_name.strip()
                for item in data.categories
                if item.category_name.strip().casefold() in existing_names
            ]

            if duplicate_names:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "These ticket categories already exist: "
                        + ", ".join(duplicate_names)
                    )
                )

            existing_quantity = sum(
                int(item["quantity"]) for item in existing_categories
            )

            new_quantity = sum(
                int(item.quantity) for item in data.categories
            )

            total_quantity = existing_quantity + new_quantity

            if total_quantity > event["venue_capacity"]:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Total ticket quantity ({total_quantity}) exceeds "
                        f"venue capacity ({event['venue_capacity']}). "
                        f"Remaining capacity: "
                        f"{event['venue_capacity'] - existing_quantity}"
                    )
                )

            created_categories = []

            for item in data.categories:
                category_name = item.category_name.strip()

                if not category_name:
                    raise HTTPException(
                        status_code=400,
                        detail="Category name cannot be empty"
                    )

                if item.price < 0 or item.quantity <= 0:
                    raise HTTPException(
                        status_code=400,
                        detail="Price must be zero or more and quantity must be positive"
                    )

                cursor.execute("""
                    INSERT INTO ticket_categories
                        (event_id, category_name, price, quantity)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, event_id, category_name, price, quantity
                """, (
                    event_id,
                    category_name,
                    item.price,
                    item.quantity
                ))

                created_categories.append(cursor.fetchone())

    return {
        "message": "Ticket categories added successfully",
        "event_id": event_id,
        "added_count": len(created_categories),
        "total_category_quantity": total_quantity,
        "venue_capacity": event["venue_capacity"],
        "categories": created_categories
    }
# --------------------------------------------------
# VIEW TICKET CATEGORIES FOR A PUBLISHED EVENT
# --------------------------------------------------

@router.get("/{event_id}/ticket-categories")
def get_event_ticket_categories(event_id: int):

    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT id
                FROM events
                WHERE id = %s AND status = 'PUBLISHED'
                """,
                (event_id,)
            )

            event = cursor.fetchone()

            if event is None:
                raise HTTPException(
                    status_code=404,
                    detail="Published event not found"
                )

            cursor.execute(
                """
                SELECT
                    tc.id,
                    tc.event_id,
                    tc.category_name,
                    tc.price,
                    tc.quantity,
                    COALESCE(s.sold_count, 0) AS sold_count,
                    GREATEST(
                        tc.quantity - COALESCE(s.sold_count, 0),
                        0
                    ) AS available_quantity
                FROM ticket_categories tc
                LEFT JOIN (
                    SELECT category_id, COUNT(*) AS sold_count
                    FROM tickets
                    WHERE status IN ('VALID', 'USED')
                    GROUP BY category_id
                ) s ON s.category_id = tc.id
                WHERE tc.event_id = %s
                ORDER BY tc.price ASC
                """,
                (event_id,)
            )

            categories = cursor.fetchall()

    return {
        "event_id": event_id,
        "total_categories": len(categories),
        "categories": categories
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

@router.post("/{event_id}/ticket-categories", status_code=201)
def create_ticket_categories(
    event_id: int,
    data: TicketCategoriesCreate,
    current_user=Depends(require_roles("ADMIN", "ORGANISER"))
):

    category_names = [
        category.category_name.strip().lower()
        for category in data.categories
    ]

    if len(category_names) != len(set(category_names)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate ticket category names are not allowed"
        )

    total_quantity = sum(
        category.quantity for category in data.categories
    )

    with get_db_connection() as connection:
        with connection.cursor() as cursor:

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
                raise HTTPException(status_code=404, detail="Event not found")

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
                    detail="Ticket categories can only be added to draft events"
                )

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
                raise HTTPException(status_code=404, detail="Venue not found")

            if total_quantity > venue["capacity"]:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Total ticket quantity exceeds venue capacity",
                        "venue_capacity": venue["capacity"],
                        "requested_tickets": total_quantity
                    }
                )

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

            created_categories = []

            for category in data.categories:
                cursor.execute(
                    """
                    INSERT INTO ticket_categories (
                        event_id, category_name, price, quantity
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

                created_categories.append(cursor.fetchone())

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
    current_user=Depends(require_roles("ADMIN", "ORGANISER"))
):

    with get_db_connection() as connection:
        with connection.cursor() as cursor:

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
                raise HTTPException(status_code=404, detail="Event not found")

            if (
                current_user["role"] != "ADMIN"
                and existing_event["created_by"] != current_user["id"]
            ):
                raise HTTPException(
                    status_code=403,
                    detail="You cannot manage this event"
                )

            if existing_event["status"] != "DRAFT":
                raise HTTPException(
                    status_code=400,
                    detail="Only draft events can be updated"
                )

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
                raise HTTPException(status_code=404, detail="Venue not found")

            buffer = timedelta(minutes=TURNAROUND_BUFFER_MINUTES)

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
    current_user=Depends(require_roles("ADMIN", "ORGANISER"))
):

    with get_db_connection() as connection:
        with connection.cursor() as cursor:

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
                raise HTTPException(status_code=404, detail="Event not found")

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
                raise HTTPException(status_code=404, detail="Venue not found")

            if category_info["total_quantity"] > venue["capacity"]:
                raise HTTPException(
                    status_code=400,
                    detail="Ticket quantity exceeds venue capacity"
                )

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
# UNPUBLISH EVENT
# --------------------------------------------------
@router.post("/{event_id}/unpublish")
def unpublish_event(
    event_id: int,
    current_user=Depends(require_roles("ADMIN", "ORGANISER"))
):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
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
                raise HTTPException(status_code=404, detail="Event not found")

            if (
                current_user["role"] != "ADMIN"
                and event["created_by"] != current_user["id"]
            ):
                raise HTTPException(
                    status_code=403,
                    detail="You cannot manage this event"
                )

            if event["status"] != "PUBLISHED":
                raise HTTPException(
                    status_code=400,
                    detail="Only published events can be unpublished"
                )

            cursor.execute(
                """
                SELECT COUNT(*) AS booking_count
                FROM bookings
                WHERE event_id = %s
                  AND status != 'CANCELLED'
                """,
                (event_id,)
            )
            activity = cursor.fetchone()

            if activity["booking_count"] > 0:
                raise HTTPException(
                    status_code=409,
                    detail="Published events with bookings cannot be unpublished"
                )

            cursor.execute(
                """
                UPDATE events
                SET status = 'DRAFT'
                WHERE id = %s
                RETURNING *
                """,
                (event_id,)
            )
            draft_event = cursor.fetchone()

    return {
        "message": "Event unpublished successfully",
        "event": draft_event
    }


# --------------------------------------------------
# CANCEL EVENT
# --------------------------------------------------

@router.post("/{event_id}/cancel")
def cancel_event(
    event_id: int,
    current_user=Depends(require_roles("ADMIN", "ORGANISER"))
):

    with get_db_connection() as connection:
        with connection.cursor() as cursor:

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
                raise HTTPException(status_code=404, detail="Event not found")

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
