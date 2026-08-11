from app.agents.critic import Critique
from app.schemas import TripOption, TripPlanRequest
from app.tools import FareOption, TravelPlanningToolRouter


class ItineraryAgent:
    def __init__(self, tools: TravelPlanningToolRouter):
        self.tools = tools

    def run(
        self,
        request: TripPlanRequest,
        fares: list[FareOption],
    ) -> list[TripOption]:
        return self.tools.build_itinerary(request, fares)

    def revise(
        self,
        request: TripPlanRequest,
        trip: TripOption,
        critique: Critique,
    ) -> TripOption:
        if critique.approved:
            return trip

        return self.tools.revise_itinerary(
            request=request,
            trip=trip,
            critic_score=critique.score,
            issues=critique.issues,
            recommendations=critique.recommendations,
        )
