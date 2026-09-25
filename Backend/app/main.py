import json
import logging
from time import perf_counter
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request

from app.config import backend_configuration_status
from app.history import TripPlanHistoryStore
from app.jobs import TripPlanJobRunner, durable_job_queue_enabled
from app.planner import create_trip_plan
from app.runs import TripPlanRunStore
from app.schemas import (
    MemoryNote,
    SavedTripPlan,
    TripPlanRequest,
    TripPlanResponse,
    TripPlanRunSnapshot,
)

LOGGER = logging.getLogger(__name__)
API_LOGGER = logging.getLogger("travel_planner.api")

history_store = TripPlanHistoryStore.from_environment()
run_store = TripPlanRunStore.from_environment(
    fail_running_on_load=not durable_job_queue_enabled()
)
job_runner = TripPlanJobRunner.from_environment(run_store, history_store)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        job_runner.shutdown()


app = FastAPI(title="Travel Planner Agent API", lifespan=lifespan)


@app.middleware("http")
async def log_api_request(request: Request, call_next):
    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        API_LOGGER.exception(
            "api_request_failed %s",
            json.dumps(
                {
                    "method": request.method,
                    "path": request.url.path,
                },
                sort_keys=True,
            ),
        )
        raise

    duration_ms = round((perf_counter() - started_at) * 1000, 2)
    API_LOGGER.info(
        "api_request %s",
        json.dumps(
            {
                "durationMs": duration_ms,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
            },
            sort_keys=True,
        ),
    )
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config/status")
async def config_status() -> dict[str, Any]:
    return backend_configuration_status()


@app.post("/trip-plans", response_model=TripPlanResponse)
async def trip_plans(request: TripPlanRequest) -> TripPlanResponse:
    response = create_trip_plan(request)
    save_trip_plan_history(request, response)
    return response


@app.get("/trip-plans/history", response_model=list[SavedTripPlan])
async def trip_plan_history(
    limit: int = Query(default=20, ge=1, le=100),
    traveler_id: str | None = Query(default=None, alias="travelerId"),
) -> list[SavedTripPlan]:
    return history_store.recent(limit=limit, traveler_id=traveler_id)


@app.get("/trip-plans/history/{plan_id}", response_model=SavedTripPlan)
async def saved_trip_plan(
    plan_id: str,
    traveler_id: str | None = Query(default=None, alias="travelerId"),
) -> SavedTripPlan:
    record = history_store.get(plan_id, traveler_id=traveler_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Saved trip plan not found.")

    return record


@app.get("/memory/latest", response_model=list[MemoryNote])
async def latest_memory(
    traveler_id: str | None = Query(default=None, alias="travelerId"),
) -> list[MemoryNote]:
    return history_store.latest_memory(traveler_id=traveler_id)


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


def save_trip_plan_history(
    request: TripPlanRequest,
    response: TripPlanResponse,
) -> None:
    try:
        history_store.save(request, response)
    except Exception:
        LOGGER.exception("Failed to persist completed trip plan.")
