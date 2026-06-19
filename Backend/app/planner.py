from app.schemas import MemoryNote, TripPlanRequest, TripPlanResponse
from app.tools import build_itinerary, search_flights


def create_trip_plan(request: TripPlanRequest) -> TripPlanResponse:
    fares = search_flights(request)
    trips = build_itinerary(request, fares)

    memory = request.memory
    if request.rememberPreferences and trips:
        best_trip = trips[0]
        memory = [
            MemoryNote(
                title="Travel preference",
                detail=(
                    f"{request.origin} departures, "
                    f"{request.mood.lower()} trips, "
                    f"${request.budget:,.0f} budget ceiling."
                ),
            ),
            MemoryNote(
                title="Constraint",
                detail=request.constraints or "No extra constraints saved.",
            ),
            MemoryNote(
                title="Last best option",
                detail=(
                    f"{best_trip.name} to {request.destination} "
                    f"at ${best_trip.fare:,.0f}."
                ),
            ),
        ]

    return TripPlanResponse(trips=trips, memory=memory)
