from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MemoryNote(BaseModel):
    title: str
    detail: str


class TripPlanRequest(BaseModel):
    origin: str
    destination: str
    departDate: datetime
    returnDate: datetime
    budget: float = Field(gt=0)
    constraints: str = ""
    rememberPreferences: bool = True
    mood: str
    memory: list[MemoryNote] = Field(default_factory=list)


class TripDay(BaseModel):
    label: str
    title: str
    detail: str


class TripOption(BaseModel):
    name: str
    route: str
    fare: float
    score: int
    meta: str
    days: list[TripDay]


class DestinationResearch(BaseModel):
    destination: str
    summary: str
    highlights: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    local_tips: list[str] = Field(default_factory=list)


class TripPlanResponse(BaseModel):
    trips: list[TripOption]
    memory: Optional[list[MemoryNote]] = None


class SavedTripPlan(BaseModel):
    id: str
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
