from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator


class VenueHireRequest(BaseModel):

    venue_id: int = Field(gt=0)
    start_time: datetime
    end_time: datetime
    purpose: str = Field(min_length=3, max_length=250)
    guest_count: int = Field(gt=0, le=10000)

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError("Timezone is required.")
        return value

    @model_validator(mode="after")
    def validate_period(self):
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time.")
        return self