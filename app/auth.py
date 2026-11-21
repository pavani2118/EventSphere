
from datetime import datetime, timedelta, timezone
import logging
import psycopg

from fastapi import HTTPException, status

from app.database import get_db_connection
from app.security import (
    hash_password,
    verify_password,
    generate_access_token,
    hash_access_token
)


logger = logging.getLogger(__name__)


def register_user(full_name: str, email: str, password: str):
    password_hash = hash_password(password)

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (
                    full_name,
                    email,
                    password_hash,
                    role
                )
                VALUES (%s, %s, %s, 'ATTENDEE')
                ON CONFLICT (email) DO NOTHING
                RETURNING id, full_name, email, role
                """,
                (full_name, email, password_hash)
            )

            user = cursor.fetchone()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists"
        )

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO notifications (
                        user_id,
                        message,
                        is_read,
                        created_at
                    )
                    VALUES (%s, %s, FALSE, NOW())
                    """,
                    (
                        user["id"],
                        "Welcome to EventSphere! Your attendee account "
                        "has been created successfully."
                    )
                )
    except psycopg.Error as error:
        logger.warning(
            "Registration notification could not be created: %s",
            error
        )

    return user


def login_user(email: str, password: str):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, full_name, email, password_hash, role
                FROM users
                WHERE email = %s AND is_active = TRUE
                """,
                (email,)
            )

            user = cursor.fetchone()

    if user is None or not verify_password(
        password,
        user["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    token = generate_access_token()
    token_hash = hash_access_token(token)

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_sessions (
                    user_id,
                    token_hash,
                    expires_at
                )
                VALUES (%s, %s, %s)
                """,
                (user["id"], token_hash, expires_at)
            )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 604800,
        "user": {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "role": user["role"]
        }
    }


def get_user_from_token(token: str):
    token_hash = hash_access_token(token)

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    u.id,
                    u.full_name,
                    u.email,
                    u.role
                FROM users u
                JOIN user_sessions s
                    ON s.user_id = u.id
                WHERE s.token_hash = %s
                  AND s.expires_at > CURRENT_TIMESTAMP
                  AND u.is_active = TRUE
                """,
                (token_hash,)
            )

            user = cursor.fetchone()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token"
        )

    return user


def logout_user(token: str):
    token_hash = hash_access_token(token)

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM user_sessions
                WHERE token_hash = %s
                """,
                (token_hash,)
            )
