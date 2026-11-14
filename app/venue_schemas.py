
from decimal import Decimal
from pydantic import BaseModel, Field


class VenueCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    location: str = Field(min_length=2)
    capacity: int = Field(gt=0)
    description: str | None = None
    image_path: str | None = None
    hourly_rate: Decimal = Field(ge=0)
    private_hire_available: bool = True


class VenueUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    location: str = Field(min_length=2)
    capacity: int = Field(gt=0)
    description: str | None = None
    image_path: str | None = None
    hourly_rate: Decimal = Field(ge=0)
    private_hire_available: bool = True
