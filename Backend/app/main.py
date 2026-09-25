from fastapi import BackgroundTasks, FastAPI, HTTPException

from app.planner import create_trip_plan
from app.runs import TripPlanRunStore
from app.schemas import TripPlanRequest, TripPlanResponse, TripPlanRunSnapshot

app = FastAPI(title="Travel Planner Agent API")
run_store = TripPlanRunStore()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/trip-plans", response_model=TripPlanResponse)
async def trip_plans(request: TripPlanRequest) -> TripPlanResponse:
    return create_trip_plan(request)


@app.post("/trip-plans/runs", response_model=TripPlanRunSnapshot)
async def create_trip_plan_run(
    request: TripPlanRequest,
    background_tasks: BackgroundTasks,
) -> TripPlanRunSnapshot:
    snapshot = run_store.create()
    background_tasks.add_task(run_trip_plan, snapshot.runId, request)
    return snapshot


@app.get("/trip-plans/runs/{run_id}", response_model=TripPlanRunSnapshot)
async def trip_plan_run(run_id: str) -> TripPlanRunSnapshot:
    return snapshot_or_404(run_id)


@app.get("/trip-plans/runs/{run_id}/events", response_model=TripPlanRunSnapshot)
async def trip_plan_run_events(run_id: str) -> TripPlanRunSnapshot:
    return snapshot_or_404(run_id)


def run_trip_plan(run_id: str, request: TripPlanRequest) -> None:
    try:
        result = create_trip_plan(
            request,
            progress=lambda step, status, title, detail: run_store.emit(
                run_id=run_id,
                step=step,
                status=status,
                title=title,
                detail=detail,
            ),
        )
        run_store.complete(run_id, result)
    except Exception as error:
        run_store.fail(run_id, str(error))


def snapshot_or_404(run_id: str) -> TripPlanRunSnapshot:
    snapshot = run_store.snapshot(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Trip plan run not found.")

    return snapshot
