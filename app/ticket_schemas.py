from decimal import Decimal

from pydantic import BaseModel, Field


class TicketCategoryCreate(BaseModel):
    category_name: str = Field(
        min_length=2,
        max_length=100
    )

    price: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2
    )

    quantity: int = Field(gt=0)


class TicketCategoriesCreate(BaseModel):
    categories: list[TicketCategoryCreate] = Field(
        min_length=1
    )


class CheckInRequest(BaseModel):
    qr_token: str = Field(
        min_length=20,
        max_length=200
    )