from fastapi import FastAPI

from app.planner import create_trip_plan
from app.schemas import TripPlanRequest, TripPlanResponse

app = FastAPI(title="Travel Planner Agent API")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/trip-plans", response_model=TripPlanResponse)
async def trip_plans(request: TripPlanRequest) -> TripPlanResponse:
    return create_trip_plan(request)
