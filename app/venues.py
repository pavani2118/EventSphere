
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.errors import ForeignKeyViolation

from app.database import get_db_connection
from app.schemas import UserResponse
from app.venue_schemas import VenueCreate, VenueUpdate
from app.dependencies import require_roles


router = APIRouter(
    prefix="/venues",
    tags=["Venue Management"]
)


# CREATE VENUE
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_venue(
    venue: VenueCreate,
    current_user=Depends(
        require_roles("ADMIN", "ORGANISER")
    )
):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO venues (
                    name,
                    location,
                    capacity,
                    description,
                    image_path,
                    hourly_rate,
                    private_hire_available
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    venue.name,
                    venue.location,
                    venue.capacity,
                    venue.description,
                    venue.image_path,
                    venue.hourly_rate,
                    venue.private_hire_available
                )
            )

            new_venue = cursor.fetchone()

    return {
        "message": "Venue created successfully",
        "venue": new_venue
    }


# GET ALL VENUES
@router.get("/")
def get_all_venues():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM venues
                ORDER BY id DESC
                """
            )

            venues = cursor.fetchall()

    return {
        "total": len(venues),
        "venues": venues
    }


# GET ONE VENUE
@router.get("/{venue_id}")
def get_venue(venue_id: int):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM venues
                WHERE id = %s
                """,
                (venue_id,)
            )

            venue = cursor.fetchone()

    if venue is None:
        raise HTTPException(
            status_code=404,
            detail="Venue not found"
        )

    return venue


# UPDATE VENUE
@router.put("/{venue_id}")
def update_venue(
    venue_id: int,
    venue: VenueUpdate,
    current_user=Depends(
        require_roles("ADMIN", "ORGANISER")
    )
):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE venues
                SET
                    name = %s,
                    location = %s,
                    capacity = %s,
                    description = %s,
                    image_path = %s,
                    hourly_rate = %s,
                    private_hire_available = %s
                WHERE id = %s
                RETURNING *
                """,
                (
                    venue.name,
                    venue.location,
                    venue.capacity,
                    venue.description,
                    venue.image_path,
                    venue.hourly_rate,
                    venue.private_hire_available,
                    venue_id
                )
            )

            updated_venue = cursor.fetchone()

    if updated_venue is None:
        raise HTTPException(
            status_code=404,
            detail="Venue not found"
        )

    return {
        "message": "Venue updated successfully",
        "venue": updated_venue
    }


# DELETE VENUE
@router.delete("/{venue_id}")
def delete_venue(
    venue_id: int,
    current_user=Depends(
        require_roles("ADMIN", "ORGANISER")
    )
):
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM venues
                    WHERE id = %s
                    RETURNING id
                    """,
                    (venue_id,)
                )

                deleted_venue = cursor.fetchone()

    except ForeignKeyViolation:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete this venue because it is linked to existing events or hire requests"
        )

    if deleted_venue is None:
        raise HTTPException(
            status_code=404,
            detail="Venue not found"
        )

    return {
        "message": "Venue deleted successfully",
        "venue_id": venue_id
    }
