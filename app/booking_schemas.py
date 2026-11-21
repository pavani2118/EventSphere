
from pydantic import BaseModel, Field


class BookingCreate(BaseModel):
    event_id: int = Field(gt=0)

    category_id: int = Field(gt=0)

    quantity: int = Field(
        gt=0,
        le=10,
        description="Number of tickets to book (maximum 10)"
    )

    payment_result: str = Field(
        default="SUCCESS",
        pattern="^(SUCCESS|FAILED)$",
        description="Simulated payment outcome"
    )


class PaymentSimulationRequest(BaseModel):
    payment_result: str = Field(
        pattern="^(SUCCESS|FAILED)$",
        description="Simulated payment outcome"
    )
    category_id: int = Field(
        gt=0,
        description="Ticket category for ticket generation"
    )
