from dataclasses import dataclass

from app.schemas import TripDay, TripOption, TripPlanRequest


@dataclass(frozen=True)
class FareOption:
    name: str
    fare: float
    score: int
    meta: str


def search_flights(request: TripPlanRequest) -> list[FareOption]:
    base_fare = max(320, round(request.budget * 0.42))
    duration = trip_duration(request)

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


def build_itinerary(
    request: TripPlanRequest,
    fares: list[FareOption],
) -> list[TripOption]:
    focus = focus_items(request.mood)
    route = f"{request.origin} -> {request.destination}"

    return [
        TripOption(
            name=fare.name,
            route=route,
            fare=fare.fare,
            score=fare.score,
            meta=fare.meta,
            days=trip_days(fare.name, focus),
        )
        for fare in fares
    ]


def trip_duration(request: TripPlanRequest) -> int:
    duration = (request.returnDate - request.departDate).days
    return min(max(duration, 3), 10)


def focus_items(mood: str) -> list[str]:
    normalized_mood = mood.lower()
    if normalized_mood == "food":
        return ["market crawl", "chef counter", "dessert stop"]
    if normalized_mood == "recharge":
        return ["spa morning", "garden walk", "slow cafe"]
    return ["tile museum", "old town walk", "riverfront concert"]


def trip_days(plan_name: str, focus: list[str]) -> list[TripDay]:
    if plan_name == "Lowest Fare":
        return [
            TripDay(label="D1", title="Fly lean", detail="Carry-on timing with a low-risk connection window."),
            TripDay(label="D2", title="Local layer", detail=f"{focus[0]} plus a neighborhood dinner reservation."),
            TripDay(label="D3", title="Flexible finish", detail="Open morning held for weather or saved recommendations."),
        ]

    if plan_name == "Comfort Pick":
        return [
            TripDay(label="D1", title="Direct arrival", detail="Midday landing, easy transfer, no late-night commitments."),
            TripDay(label="D2", title="Prime slot", detail=f"{focus[1]} anchored by the highest-fit booking window."),
            TripDay(label="D3", title="Buffer day", detail=f"{focus[2]} with an airport transfer already staged."),
        ]

    return [
        TripDay(label="D1", title="Arrive light", detail=f"{focus[0]} after check-in, early dinner near the hotel."),
        TripDay(label="D2", title="Deep day", detail=f"{focus[1]} with a protected two-hour open block."),
        TripDay(label="D3", title="Easy close", detail=f"{focus[2]} before a late afternoon return."),
    ]
