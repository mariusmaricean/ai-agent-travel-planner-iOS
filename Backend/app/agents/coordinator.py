from typing import Callable

from app.agents.critic import ItineraryCriticAgent
from app.agents.itinerary import ItineraryAgent
from app.agents.research import DestinationResearchAgent
from app.schemas import DestinationResearch, MemoryNote, TripOption, TripPlanRequest, TripPlanResponse
from app.tools import TravelPlanningToolRouter, add_meta_flag, default_tool_router

ProgressEmitter = Callable[[str, str, str, str], None]
DEFAULT_MAX_REVISION_PASSES = 2


class TripCoordinatorAgent:
    def __init__(
        self,
        tools: TravelPlanningToolRouter = default_tool_router,
        research_agent: DestinationResearchAgent | None = None,
        itinerary_agent: ItineraryAgent | None = None,
        critic_agent: ItineraryCriticAgent | None = None,
        progress: ProgressEmitter | None = None,
        max_revision_passes: int = DEFAULT_MAX_REVISION_PASSES,
    ):
        self.tools = tools
        self.research_agent = research_agent or DestinationResearchAgent(tools)
        self.itinerary_agent = itinerary_agent or ItineraryAgent(tools)
        self.critic_agent = critic_agent or ItineraryCriticAgent()
        self.progress = progress
        self.max_revision_passes = max(1, max_revision_passes)

    def run(self, request: TripPlanRequest) -> TripPlanResponse:
        self.emit(
            step="research",
            status="active",
            title="Research destination",
            detail=f"Studying {request.destination} for {request.mood.lower()} goals.",
        )
        destination_research = self.research_agent.run(request)
        self.emit(
            step="research",
            status="done",
            title="Research destination",
            detail=destination_research.summary,
        )

        self.emit(
            step="flights",
            status="active",
            title="Search flights",
            detail=f"Checking {request.origin} to {request.destination} fare options.",
        )
        fares = self.tools.search_flights(request)
        self.emit(
            step="flights",
            status="done",
            title="Search flights",
            detail=f"Found {len(fares)} fare option{'' if len(fares) == 1 else 's'}.",
        )

        self.emit(
            step="itinerary",
            status="active",
            title="Build itinerary",
            detail="Turning fares and destination research into trip options.",
        )
        trips = self.itinerary_agent.run(request, fares, destination_research)
        self.emit(
            step="itinerary",
            status="done",
            title="Build itinerary",
            detail=f"Built {len(trips)} itinerary option{'' if len(trips) == 1 else 's'}.",
        )

        self.emit(
            step="critic",
            status="active",
            title="Critic review",
            detail="Checking budget, constraints, pacing, and missing days.",
        )
        reviewed_trips: list[TripOption] = []
        revision_count = 0
        for trip in trips:
            reviewed_trip, did_revise = self.review_trip(request, trip, destination_research)
            reviewed_trips.append(reviewed_trip)
            if did_revise:
                revision_count += 1

        self.emit(
            step="critic",
            status="done",
            title="Critic review",
            detail=f"Reviewed {len(reviewed_trips)} trip option{'' if len(reviewed_trips) == 1 else 's'}.",
        )

        if revision_count == 0:
            self.emit(
                step="revision",
                status="done",
                title="Revise if needed",
                detail="No revision needed.",
            )

        self.emit(
            step="memory",
            status="active",
            title="Finalize memory",
            detail="Preparing traveler memory updates.",
        )
        memory = self.updated_memory(request, reviewed_trips)
        self.emit(
            step="memory",
            status="done",
            title="Finalize memory",
            detail="Memory update ready." if request.rememberPreferences else "Memory unchanged.",
        )

        return TripPlanResponse(
            trips=reviewed_trips,
            memory=memory,
        )

    def review_trip(
        self,
        request: TripPlanRequest,
        trip: TripOption,
        destination_research: DestinationResearch,
    ) -> tuple[TripOption, bool]:
        critique = self.critic_agent.run(request, trip)
        if critique.approved:
            return trip, False

        revised_trip = trip
        final_critique = critique
        for revision_pass in range(1, self.max_revision_passes + 1):
            self.emit(
                step="revision",
                status="active",
                title="Revise if needed",
                detail=(
                    f"Revising {trip.name} from critic feedback "
                    f"(pass {revision_pass}/{self.max_revision_passes})."
                ),
            )
            revised_trip = self.itinerary_agent.revise(
                request,
                revised_trip,
                final_critique,
                destination_research,
            )
            final_critique = self.critic_agent.run(request, revised_trip)
            if final_critique.approved:
                break

        self.emit(
            step="revision",
            status="done",
            title="Revise if needed",
            detail=(
                f"Revised {trip.name}; final critic score "
                f"{final_critique.score}."
            ),
        )
        if final_critique.approved:
            return TripOption(
                name=revised_trip.name,
                route=revised_trip.route,
                fare=revised_trip.fare,
                score=max(revised_trip.score, final_critique.score),
                meta=revised_trip.meta,
                days=revised_trip.days,
            ), True

        return TripOption(
            name=revised_trip.name,
            route=revised_trip.route,
            fare=revised_trip.fare,
            score=final_critique.score,
            meta=add_meta_flag(revised_trip.meta, "revision-needs-review"),
            days=revised_trip.days,
        ), True

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

    def emit(self, step: str, status: str, title: str, detail: str = "") -> None:
        if self.progress is None:
            return

        self.progress(step, status, title, detail)
