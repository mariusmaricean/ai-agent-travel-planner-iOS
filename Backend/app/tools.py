from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from app.schemas import MemoryNote, TripDay, TripOption, TripPlanRequest


@dataclass(frozen=True)
class FareOption:
    name: str
    fare: float
    score: int
    meta: str


@dataclass(frozen=True)
class FlightSearchQuery:
    origin: str
    destination: str
    depart_date: datetime
    return_date: datetime
    budget: float


@dataclass(frozen=True)
class ItineraryPlanningInput:
    origin: str
    destination: str
    duration: int
    mood: str
    constraints: str
    memory: list[MemoryNote]
    fares: list[FareOption]


FlightProviderFunction = Callable[[FlightSearchQuery], list[FareOption]]
ItineraryPlannerFunction = Callable[[ItineraryPlanningInput], list[TripOption]]


@dataclass(frozen=True)
class TravelPlanningToolRouter:
    flight_provider: FlightProviderFunction
    itinerary_planner: ItineraryPlannerFunction

    def search_flights(self, request: TripPlanRequest) -> list[FareOption]:
        query = FlightSearchQuery(
            origin=request.origin,
            destination=request.destination,
            depart_date=request.departDate,
            return_date=request.returnDate,
            budget=request.budget,
        )
        return self.flight_provider(query)

    def build_itinerary(
        self,
        request: TripPlanRequest,
        fares: list[FareOption],
    ) -> list[TripOption]:
        planning_input = ItineraryPlanningInput(
            origin=request.origin,
            destination=request.destination,
            duration=trip_duration(request),
            mood=request.mood,
            constraints=request.constraints,
            memory=request.memory,
            fares=fares,
        )
        return self.itinerary_planner(planning_input)


def mock_flight_provider(query: FlightSearchQuery) -> list[FareOption]:
    base_fare = max(320, round(query.budget * 0.42))
    duration = trip_duration_from_dates(query.depart_date, query.return_date)

    return [
        FareOption(
            name="Balanced Sprint",
            fare=base_fare + 70,
            score=94,
            meta=f"{duration} days | morning outbound | 1 checked bag",
        ),
        FareOption(
            name="Lowest Fare",
            fare=base_fare - 45,
            score=88,
            meta=f"{duration} days | one connection | budget winner",
        ),
        FareOption(
            name="Comfort Pick",
            fare=base_fare + 180,
            score=91,
            meta=f"{duration} days | direct flight | aisle-friendly timing",
        ),
    ]


def rule_based_itinerary_planner(planning_input: ItineraryPlanningInput) -> list[TripOption]:
    focus = focus_items(planning_input.mood)
    route = f"{planning_input.origin} -> {planning_input.destination}"

    return [
        TripOption(
            name=fare.name,
            route=route,
            fare=fare.fare,
            score=fare.score,
            meta=fare.meta,
            days=trip_days(fare.name, focus, planning_input),
        )
        for fare in planning_input.fares
    ]


default_tool_router = TravelPlanningToolRouter(
    flight_provider=mock_flight_provider,
    itinerary_planner=rule_based_itinerary_planner,
)


def search_flights(request: TripPlanRequest) -> list[FareOption]:
    return default_tool_router.search_flights(request)


def build_itinerary(
    request: TripPlanRequest,
    fares: list[FareOption],
) -> list[TripOption]:
    return default_tool_router.build_itinerary(request, fares)


def trip_duration(request: TripPlanRequest) -> int:
    return trip_duration_from_dates(request.departDate, request.returnDate)


def trip_duration_from_dates(depart_date: datetime, return_date: datetime) -> int:
    duration = (return_date - depart_date).days
    return min(max(duration, 3), 10)


def focus_items(mood: str) -> list[str]:
    normalized_mood = mood.lower()
    if normalized_mood == "food":
        return ["market crawl", "chef counter", "dessert stop"]
    if normalized_mood == "recharge":
        return ["spa morning", "garden walk", "slow cafe"]
    return ["tile museum", "old town walk", "riverfront concert"]


def trip_days(
    plan_name: str,
    focus: list[str],
    planning_input: ItineraryPlanningInput,
) -> list[TripDay]:
    planning_note = traveler_context_note(planning_input)

    if plan_name == "Lowest Fare":
        return [
            TripDay(label="D1", title="Fly lean", detail="Carry-on timing with a low-risk connection window."),
            TripDay(label="D2", title="Local layer", detail=f"{focus[0]} plus a neighborhood dinner reservation."),
            TripDay(label="D3", title="Flexible finish", detail=planning_note),
        ]

    if plan_name == "Comfort Pick":
        return [
            TripDay(label="D1", title="Direct arrival", detail="Midday landing, easy transfer, no late-night commitments."),
            TripDay(label="D2", title="Prime slot", detail=f"{focus[1]} anchored by the highest-fit booking window."),
            TripDay(label="D3", title="Buffer day", detail=f"{focus[2]} plus {planning_note}"),
        ]

    return [
        TripDay(label="D1", title="Arrive light", detail=f"{focus[0]} after check-in, early dinner near the hotel."),
        TripDay(label="D2", title="Deep day", detail=f"{focus[1]} with a protected two-hour open block."),
        TripDay(label="D3", title="Easy close", detail=f"{focus[2]} before a late afternoon return. {planning_note}"),
    ]


def traveler_context_note(planning_input: ItineraryPlanningInput) -> str:
    if planning_input.constraints:
        return f"Constraints folded in: {planning_input.constraints}"

    if planning_input.memory:
        return f"Saved preference considered: {planning_input.memory[0].detail}"

    return "Open morning held for weather or saved recommendations."
