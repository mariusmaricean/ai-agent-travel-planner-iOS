from app.agents.coordinator import ProgressEmitter, TripCoordinatorAgent
from app.schemas import TripPlanRequest, TripPlanResponse
from app.tools import TravelPlanningToolRouter, default_tool_router


def create_trip_plan(
    request: TripPlanRequest,
    tools: TravelPlanningToolRouter = default_tool_router,
    progress: ProgressEmitter | None = None,
) -> TripPlanResponse:
    coordinator = TripCoordinatorAgent(tools=tools, progress=progress)
    return coordinator.run(request)
