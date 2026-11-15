from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db_connection
from app.dependencies import get_current_user


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"]
)


@router.get("/my-notifications")
def get_my_notifications(current_user=Depends(get_current_user)):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, message, is_read, created_at
                FROM notifications
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                """,
                (current_user["id"],)
            )
            notifications = cursor.fetchall()

    return {
        "total_notifications": len(notifications),
        "unread_notifications": sum(
            1 for notification in notifications
            if not notification["is_read"]
        ),
        "notifications": notifications
    }


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user=Depends(get_current_user)
):
    if notification_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid notification ID."
        )

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE notifications
                SET is_read = TRUE
                WHERE id = %s
                  AND user_id = %s
                RETURNING id, is_read
                """,
                (notification_id, current_user["id"])
            )
            notification = cursor.fetchone()

    if notification is None:
        raise HTTPException(
            status_code=404,
            detail="Notification not found."
        )

    return {
        "success": True,
        "notification_id": notification["id"],
        "is_read": notification["is_read"]
    }
