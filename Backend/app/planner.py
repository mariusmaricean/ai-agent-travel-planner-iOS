from app.agents import TripCoordinatorAgent
from app.schemas import TripPlanRequest, TripPlanResponse
from app.tools import TravelPlanningToolRouter, default_tool_router


def create_trip_plan(
    request: TripPlanRequest,
    tools: TravelPlanningToolRouter = default_tool_router,
) -> TripPlanResponse:
    coordinator = TripCoordinatorAgent(tools=tools)
    return coordinator.run(request)
