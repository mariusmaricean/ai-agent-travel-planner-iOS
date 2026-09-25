from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class MemoryNote(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    detail: str = Field(min_length=1, max_length=500)


class TripPlanRequest(BaseModel):
    travelerId: Optional[str] = Field(default=None, max_length=120)
    origin: str = Field(min_length=1, max_length=80)
    destination: str = Field(min_length=1, max_length=80)
    departDate: datetime
    returnDate: datetime
    budget: float = Field(gt=0, le=100_000)
    constraints: str = Field(default="", max_length=1000)
    rememberPreferences: bool = True
    mood: str = Field(min_length=1, max_length=40)
    memory: list[MemoryNote] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_date_window(self) -> "TripPlanRequest":
        if self.returnDate <= self.departDate:
            raise ValueError("returnDate must be after departDate.")

        if (self.returnDate - self.departDate).days > 30:
            raise ValueError("Trip date range cannot exceed 30 days.")

        return self


class TripDay(BaseModel):
    label: str = Field(min_length=1, max_length=12)
    title: str = Field(min_length=1, max_length=80)
    detail: str = Field(min_length=1, max_length=800)


class TripOption(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    route: str = Field(min_length=1, max_length=160)
    fare: float
    score: int
    meta: str = Field(max_length=240)
    days: list[TripDay] = Field(default_factory=list, max_length=30)


class DestinationResearch(BaseModel):
    destination: str = Field(max_length=80)
    summary: str = Field(max_length=2000)
    highlights: list[str] = Field(default_factory=list, max_length=20)
    cautions: list[str] = Field(default_factory=list, max_length=20)
    local_tips: list[str] = Field(default_factory=list, max_length=20)


class TripPlanResponse(BaseModel):
    trips: list[TripOption] = Field(default_factory=list, max_length=10)
    memory: Optional[list[MemoryNote]] = None


class SavedTripPlan(BaseModel):
    id: str
    travelerId: str = "local"
    request: TripPlanRequest
    response: TripPlanResponse
    createdAt: datetime
    runId: Optional[str] = None


class AgentRunEvent(BaseModel):
    id: int
    step: str
    status: str
    title: str
    detail: str = ""
    createdAt: datetime


class TripPlanRunSnapshot(BaseModel):
    runId: str
    status: str
    events: list[AgentRunEvent] = Field(default_factory=list)
    result: Optional[TripPlanResponse] = None
    error: Optional[str] = None


class TripPlanJobRecord(BaseModel):
    runId: str
    request: TripPlanRequest
    status: str
    attempts: int = 0
    createdAt: datetime
    updatedAt: datetime
    lastError: Optional[str] = None
