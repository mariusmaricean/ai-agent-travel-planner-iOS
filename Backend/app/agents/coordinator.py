from app.agents.critic import ItineraryCriticAgent
from app.agents.itinerary import ItineraryAgent
from app.schemas import MemoryNote, TripOption, TripPlanRequest, TripPlanResponse
from app.tools import TravelPlanningToolRouter, default_tool_router


class TripCoordinatorAgent:
    def __init__(
        self,
        tools: TravelPlanningToolRouter = default_tool_router,
        itinerary_agent: ItineraryAgent | None = None,
        critic_agent: ItineraryCriticAgent | None = None,
    ):
        self.tools = tools
        self.itinerary_agent = itinerary_agent or ItineraryAgent(tools)
        self.critic_agent = critic_agent or ItineraryCriticAgent()

    def run(self, request: TripPlanRequest) -> TripPlanResponse:
        fares = self.tools.search_flights(request)
        trips = self.itinerary_agent.run(request, fares)
        reviewed_trips = [self.review_trip(request, trip) for trip in trips]

        return TripPlanResponse(
            trips=reviewed_trips,
            memory=self.updated_memory(request, reviewed_trips),
        )

    def review_trip(
        self,
        request: TripPlanRequest,
        trip: TripOption,
    ) -> TripOption:
        critique = self.critic_agent.run(request, trip)
        if critique.approved:
            return trip

        return self.itinerary_agent.revise(request, trip, critique)

    def updated_memory(
        self,
        request: TripPlanRequest,
        trips: list[TripOption],
    ) -> list[MemoryNote]:
        if not request.rememberPreferences or not trips:
            return request.memory

        best_trip = trips[0]
        return [
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
