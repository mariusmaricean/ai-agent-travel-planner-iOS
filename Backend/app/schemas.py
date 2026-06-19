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


class TripPlanResponse(BaseModel):
    trips: list[TripOption]
    memory: Optional[list[MemoryNote]] = None
