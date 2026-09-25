from app.agents.critic import ItineraryCriticAgent
from app.agents.itinerary import ItineraryAgent
from app.agents.research import DestinationResearchAgent
from app.schemas import DestinationResearch, MemoryNote, TripOption, TripPlanRequest, TripPlanResponse
from app.tools import TravelPlanningToolRouter, add_meta_flag, default_tool_router


class TripCoordinatorAgent:
    def __init__(
        self,
        tools: TravelPlanningToolRouter = default_tool_router,
        research_agent: DestinationResearchAgent | None = None,
        itinerary_agent: ItineraryAgent | None = None,
        critic_agent: ItineraryCriticAgent | None = None,
    ):
        self.tools = tools
        self.research_agent = research_agent or DestinationResearchAgent(tools)
        self.itinerary_agent = itinerary_agent or ItineraryAgent(tools)
        self.critic_agent = critic_agent or ItineraryCriticAgent()

    def run(self, request: TripPlanRequest) -> TripPlanResponse:
        destination_research = self.research_agent.run(request)
        fares = self.tools.search_flights(request)
        trips = self.itinerary_agent.run(request, fares, destination_research)
        reviewed_trips = [
            self.review_trip(request, trip, destination_research)
            for trip in trips
        ]

        return TripPlanResponse(
            trips=reviewed_trips,
            memory=self.updated_memory(request, reviewed_trips),
        )

    def review_trip(
        self,
        request: TripPlanRequest,
        trip: TripOption,
        destination_research: DestinationResearch,
    ) -> TripOption:
        critique = self.critic_agent.run(request, trip)
        if critique.approved:
            return trip

        revised_trip = self.itinerary_agent.revise(request, trip, critique, destination_research)
        final_critique = self.critic_agent.run(request, revised_trip)
        if final_critique.approved:
            return TripOption(
                name=revised_trip.name,
                route=revised_trip.route,
                fare=revised_trip.fare,
                score=max(revised_trip.score, final_critique.score),
                meta=revised_trip.meta,
                days=revised_trip.days,
            )

        return TripOption(
            name=revised_trip.name,
            route=revised_trip.route,
            fare=revised_trip.fare,
            score=final_critique.score,
            meta=add_meta_flag(revised_trip.meta, "revision-needs-review"),
            days=revised_trip.days,
        )

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
