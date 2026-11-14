from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class EventBase(BaseModel):

    title: str = Field(min_length=3, max_length=200)

    category: str = Field(min_length=2, max_length=100)

    venue_id: int = Field(gt=0)

    start_time: datetime

    end_time: datetime

    description: str | None = None

    @model_validator(mode="after")
    def validate_event_time(self):

        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("Event times must include a timezone")

        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")

        return self


class EventCreate(EventBase):
    pass


class EventUpdate(EventBase):
    pass