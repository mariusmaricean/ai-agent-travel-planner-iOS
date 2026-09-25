from app.agents.critic import Critique
from app.schemas import DestinationResearch, TripOption, TripPlanRequest
from app.tools import FareOption, TravelPlanningToolRouter


class ItineraryAgent:
    def __init__(self, tools: TravelPlanningToolRouter):
        self.tools = tools

    def run(
        self,
        request: TripPlanRequest,
        fares: list[FareOption],
        destination_research: DestinationResearch | None = None,
    ) -> list[TripOption]:
        return self.tools.build_itinerary(request, fares, destination_research)

    def revise(
        self,
        request: TripPlanRequest,
        trip: TripOption,
        critique: Critique,
        destination_research: DestinationResearch | None = None,
    ) -> TripOption:
        if critique.approved:
            return trip

        return self.tools.revise_itinerary(
            request=request,
            trip=trip,
            critic_score=critique.score,
            issues=critique.issues,
            recommendations=critique.recommendations,
            destination_research=destination_research,
        )
