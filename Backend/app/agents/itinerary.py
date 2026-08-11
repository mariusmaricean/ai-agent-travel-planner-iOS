from app.agents.critic import Critique
from app.schemas import TripDay, TripOption, TripPlanRequest
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
        trip: TripOption,
        critique: Critique,
    ) -> TripOption:
        if critique.approved or not critique.recommendations:
            return trip

        days = list(trip.days)
        if days:
            last_day = days[-1]
            days[-1] = TripDay(
                label=last_day.label,
                title=last_day.title,
                detail=(
                    f"{last_day.detail} Critic revision: "
                    f"{critique.recommendations[0]}"
                ),
            )

        return TripOption(
            name=trip.name,
            route=trip.route,
            fare=trip.fare,
            score=max(critique.score, min(trip.score, 90)),
            meta=f"{trip.meta} | critic-reviewed",
            days=days,
        )
