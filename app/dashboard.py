
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
