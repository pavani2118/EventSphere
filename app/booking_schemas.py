
from pydantic import BaseModel, Field


class BookingCreate(BaseModel):
    event_id: int = Field(gt=0)

    category_id: int = Field(gt=0)

    quantity: int = Field(
        gt=0,
        le=10,
        description="Number of tickets to book (maximum 10)"
    )
