
from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db_connection
from app.dependencies import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def check_admin(current_user):
    role = (
        current_user.get("role")
        if isinstance(current_user, dict)
        else getattr(current_user, "role", None)
    )

    if role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )


@router.get("/admin/summary")
def get_admin_summary(current_user=Depends(get_current_user)):
    check_admin(current_user)

    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute("SELECT COUNT(*) AS total_users FROM users")
            users = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) AS total_venues FROM venues")
            venues = cursor.fetchone()

            cursor.execute("""
                SELECT COUNT(*) AS total_events,
                       COUNT(*) FILTER (
                           WHERE status = 'PUBLISHED'
                       ) AS published_events
                FROM events
            """)
            events = cursor.fetchone()

            cursor.execute("""
                SELECT COUNT(*) AS total_bookings,
                       COUNT(*) FILTER (
                           WHERE status = 'CONFIRMED'
                       ) AS confirmed_bookings
                FROM bookings
            """)
            bookings = cursor.fetchone()

            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) AS total_revenue
                FROM payments
                WHERE status = 'SUCCESS'
            """)
            revenue = cursor.fetchone()

            cursor.execute("""
                SELECT COUNT(*) AS total_tickets,
                       COUNT(*) FILTER (
                           WHERE status = 'USED'
                       ) AS checked_in_tickets
                FROM tickets
            """)
            tickets = cursor.fetchone()

            cursor.execute("""
                SELECT COALESCE(SUM(tc.quantity), 0) AS total_capacity
                FROM ticket_categories tc
                JOIN events e ON e.id = tc.event_id
                WHERE e.status = 'PUBLISHED'
            """)
            capacity = cursor.fetchone()

    return {
        "total_users": users["total_users"],
        "total_venues": venues["total_venues"],
        "total_events": events["total_events"],
        "published_events": events["published_events"],
        "total_bookings": bookings["total_bookings"],
        "confirmed_bookings": bookings["confirmed_bookings"],
        "total_revenue": float(revenue["total_revenue"]),
        "total_tickets": tickets["total_tickets"],
        "checked_in_tickets": tickets["checked_in_tickets"],
        "total_capacity": capacity["total_capacity"]
    }


@router.get("/admin/agent-messages")
def get_agent_messages(current_user=Depends(get_current_user)):
    check_admin(current_user)

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, sender, receiver, performative,
                       content, conversation_id, created_at
                FROM agent_messages
                ORDER BY created_at DESC
                LIMIT 30
            """)
            messages = cursor.fetchall()

    return {
        "total": len(messages),
        "messages": messages
    }


@router.get("/admin/recent-events")
def get_recent_events(current_user=Depends(get_current_user)):
    check_admin(current_user)

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT e.id, e.title, e.category, e.status,
                       e.start_time, v.name AS venue_name
                FROM events e
                LEFT JOIN venues v ON v.id = e.venue_id
                ORDER BY e.created_at DESC
                LIMIT 10
            """)
            events = cursor.fetchall()

    return {
        "total": len(events),
        "events": events
    }


@router.get("/admin/recent-bookings")
def get_recent_bookings(current_user=Depends(get_current_user)):
    check_admin(current_user)

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT b.id AS booking_id,
                       e.title AS event_title,
                       b.quantity,
                       b.total_amount,
                       b.status,
                       b.created_at
                FROM bookings b
                JOIN events e ON e.id = b.event_id
                ORDER BY b.created_at DESC
                LIMIT 10
                """
            )
            bookings = cursor.fetchall()

    return {
        "total": len(bookings),
        "bookings": bookings
    }


@router.get("/organiser/summary")
def get_organiser_summary(
    current_user=Depends(get_current_user)
):
    if current_user["role"] != "ORGANISER":
        raise HTTPException(
            status_code=403,
            detail="Organiser access required"
        )

    organiser_id = current_user["id"]

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_events,
                    COUNT(*) FILTER (
                        WHERE status = 'PUBLISHED'
                    ) AS published_events,
                    COUNT(*) FILTER (
                        WHERE status = 'DRAFT'
                    ) AS draft_events,
                    COUNT(*) FILTER (
                        WHERE status = 'CANCELLED'
                    ) AS cancelled_events
                FROM events
                WHERE created_by = %s
                """,
                (organiser_id,)
            )
            event_stats = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    COUNT(DISTINCT b.id) AS total_bookings,
                    COUNT(DISTINCT b.id) FILTER (
                        WHERE b.status = 'CONFIRMED'
                    ) AS confirmed_bookings,
                    COUNT(t.id) AS total_tickets,
                    COUNT(t.id) FILTER (
                        WHERE t.status IN ('VALID', 'USED')
                    ) AS active_tickets
                FROM events e
                LEFT JOIN bookings b ON b.event_id = e.id
                LEFT JOIN tickets t ON t.booking_id = b.id
                WHERE e.created_by = %s
                """,
                (organiser_id,)
            )
            booking_stats = cursor.fetchone()

            cursor.execute(
                """
                SELECT COALESCE(SUM(p.amount), 0) AS total_revenue
                FROM payments p
                JOIN bookings b ON b.id = p.booking_id
                JOIN events e ON e.id = b.event_id
                WHERE e.created_by = %s
                  AND p.status = 'SUCCESS'
                """,
                (organiser_id,)
            )
            revenue = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    b.id AS booking_id,
                    b.quantity,
                    b.total_amount,
                    b.status AS booking_status,
                    b.created_at,
                    e.id AS event_id,
                    e.title AS event_title,
                    u.full_name AS attendee_name,
                    u.email AS attendee_email,
                    p.status AS payment_status
                FROM bookings b
                JOIN events e ON e.id = b.event_id
                JOIN users u ON u.id = b.user_id
                LEFT JOIN LATERAL (
                    SELECT status
                    FROM payments
                    WHERE booking_id = b.id
                    ORDER BY id DESC
                    LIMIT 1
                ) p ON TRUE
                WHERE e.created_by = %s
                ORDER BY b.created_at DESC
                LIMIT 10
                """,
                (organiser_id,)
            )
            recent_bookings = cursor.fetchall()

    return {
        "total_events": event_stats["total_events"],
        "published_events": event_stats["published_events"],
        "draft_events": event_stats["draft_events"],
        "cancelled_events": event_stats["cancelled_events"],
        "total_bookings": booking_stats["total_bookings"],
        "confirmed_bookings": booking_stats["confirmed_bookings"],
        "total_tickets": booking_stats["total_tickets"],
        "active_tickets": booking_stats["active_tickets"],
        "total_revenue": float(revenue["total_revenue"]),
        "recent_bookings": recent_bookings
    }


@router.get("/organiser/bookings")
def get_organiser_bookings(
    event_id: int | None = None,
    status: str | None = None,
    current_user=Depends(get_current_user)
):
    if current_user["role"] != "ORGANISER":
        raise HTTPException(
            status_code=403,
            detail="Organiser access required"
        )

    filters = ["e.created_by = %s"]
    params = [current_user["id"]]

    if event_id is not None:
        filters.append("e.id = %s")
        params.append(event_id)
    if status:
        filters.append("b.status = %s")
        params.append(status.upper())

    where_clause = " AND ".join(filters)

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    b.id AS booking_id,
                    b.quantity,
                    b.total_amount,
                    b.status AS booking_status,
                    b.created_at,
                    e.id AS event_id,
                    e.title AS event_title,
                    u.id AS attendee_id,
                    u.full_name AS attendee_name,
                    u.email AS attendee_email,
                    p.status AS payment_status,
                    p.payment_reference,
                    COUNT(t.id) AS ticket_count
                FROM bookings b
                JOIN events e ON e.id = b.event_id
                JOIN users u ON u.id = b.user_id
                LEFT JOIN LATERAL (
                    SELECT status, payment_reference
                    FROM payments
                    WHERE booking_id = b.id
                    ORDER BY id DESC
                    LIMIT 1
                ) p ON TRUE
                LEFT JOIN tickets t ON t.booking_id = b.id
                WHERE {where_clause}
                GROUP BY
                    b.id, b.quantity, b.total_amount, b.status, b.created_at,
                    e.id, e.title, u.id, u.full_name, u.email,
                    p.status, p.payment_reference
                ORDER BY b.created_at DESC
                """,
                tuple(params)
            )
            bookings = cursor.fetchall()

    return {
        "total": len(bookings),
        "bookings": bookings
    }
