from app.schemas import DestinationResearch, TripPlanRequest
from app.tools import TravelPlanningToolRouter


class DestinationResearchAgent:
    def __init__(self, tools: TravelPlanningToolRouter):
        self.tools = tools

    def run(self, request: TripPlanRequest) -> DestinationResearch:
        return self.tools.research_destination(request)
