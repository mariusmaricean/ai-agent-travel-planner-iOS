from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException

from app.jobs import TripPlanJobRunner
from app.planner import create_trip_plan
from app.runs import TripPlanRunStore
from app.schemas import TripPlanRequest, TripPlanResponse, TripPlanRunSnapshot

run_store = TripPlanRunStore.from_environment()
job_runner = TripPlanJobRunner.from_environment(run_store)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        job_runner.shutdown()


app = FastAPI(title="Travel Planner Agent API", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/trip-plans", response_model=TripPlanResponse)
async def trip_plans(request: TripPlanRequest) -> TripPlanResponse:
    return create_trip_plan(request)


@app.post("/trip-plans/runs", response_model=TripPlanRunSnapshot)
async def create_trip_plan_run(request: TripPlanRequest) -> TripPlanRunSnapshot:
    snapshot = run_store.create()
    job_runner.submit(snapshot.runId, request)
    return snapshot


@app.get("/trip-plans/runs/{run_id}", response_model=TripPlanRunSnapshot)
async def trip_plan_run(run_id: str) -> TripPlanRunSnapshot:
    return snapshot_or_404(run_id)


@app.get("/trip-plans/runs/{run_id}/events", response_model=TripPlanRunSnapshot)
async def trip_plan_run_events(run_id: str) -> TripPlanRunSnapshot:
    return snapshot_or_404(run_id)


def snapshot_or_404(run_id: str) -> TripPlanRunSnapshot:
    snapshot = run_store.snapshot(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Trip plan run not found.")

    return snapshot
