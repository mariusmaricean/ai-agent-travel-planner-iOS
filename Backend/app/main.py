import json
import logging
from time import perf_counter
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Header, HTTPException, Query, Request

from app.config import backend_configuration_status
from app.history import TripPlanHistoryStore
from app.jobs import TripPlanJobRunner, durable_job_queue_enabled
from app.planner import create_trip_plan
from app.runs import TripPlanRunStore
from app.schemas import (
    AccountLoginRequest,
    AccountRegistrationRequest,
    AccountSessionResponse,
    AuthenticatedUser,
    MemoryNote,
    SavedTripPlan,
    TripPlanRequest,
    TripPlanResponse,
    TripPlanRunSnapshot,
)
from app.users import (
    InvalidCredentialsError,
    UserAccountStore,
    UserAlreadyExistsError,
)

LOGGER = logging.getLogger(__name__)
API_LOGGER = logging.getLogger("travel_planner.api")

history_store = TripPlanHistoryStore.from_environment()
run_store = TripPlanRunStore.from_environment(
    fail_running_on_load=not durable_job_queue_enabled()
)
job_runner = TripPlanJobRunner.from_environment(run_store, history_store)
user_store = UserAccountStore.from_environment()


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


@app.post("/auth/register", response_model=AccountSessionResponse)
async def register_account(
    request: AccountRegistrationRequest,
) -> AccountSessionResponse:
    try:
        return user_store.register(
            email=request.email,
            password=request.password,
            display_name=request.displayName,
        )
    except UserAlreadyExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/auth/login", response_model=AccountSessionResponse)
async def login_account(request: AccountLoginRequest) -> AccountSessionResponse:
    try:
        return user_store.login(email=request.email, password=request.password)
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@app.get("/auth/me", response_model=AuthenticatedUser)
async def current_account(
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser:
    return require_authenticated_user(authorization)


@app.post("/trip-plans", response_model=TripPlanResponse)
async def trip_plans(
    request: TripPlanRequest,
    authorization: str | None = Header(default=None),
) -> TripPlanResponse:
    scoped_request = request_for_authenticated_scope(request, authorization)
    response = create_trip_plan(scoped_request)
    save_trip_plan_history(scoped_request, response)
    return response


@app.get("/trip-plans/history", response_model=list[SavedTripPlan])
async def trip_plan_history(
    limit: int = Query(default=20, ge=1, le=100),
    traveler_id: str | None = Query(default=None, alias="travelerId"),
    authorization: str | None = Header(default=None),
) -> list[SavedTripPlan]:
    return history_store.recent(
        limit=limit,
        traveler_id=traveler_scope(traveler_id, authorization),
    )


@app.get("/trip-plans/history/{plan_id}", response_model=SavedTripPlan)
async def saved_trip_plan(
    plan_id: str,
    traveler_id: str | None = Query(default=None, alias="travelerId"),
    authorization: str | None = Header(default=None),
) -> SavedTripPlan:
    record = history_store.get(
        plan_id,
        traveler_id=traveler_scope(traveler_id, authorization),
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Saved trip plan not found.")

    return record


@app.get("/memory/latest", response_model=list[MemoryNote])
async def latest_memory(
    traveler_id: str | None = Query(default=None, alias="travelerId"),
    authorization: str | None = Header(default=None),
) -> list[MemoryNote]:
    return history_store.latest_memory(
        traveler_id=traveler_scope(traveler_id, authorization),
    )


@app.post("/trip-plans/runs", response_model=TripPlanRunSnapshot)
async def create_trip_plan_run(
    request: TripPlanRequest,
    authorization: str | None = Header(default=None),
) -> TripPlanRunSnapshot:
    scoped_request = request_for_authenticated_scope(request, authorization)
    snapshot = run_store.create()
    job_runner.submit(snapshot.runId, scoped_request)
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


def request_for_authenticated_scope(
    request: TripPlanRequest,
    authorization: str | None,
) -> TripPlanRequest:
    scoped_traveler_id = traveler_scope(request.travelerId, authorization)
    return request.model_copy(update={"travelerId": scoped_traveler_id})


def traveler_scope(
    traveler_id: str | None,
    authorization: str | None,
) -> str | None:
    user = authenticated_user_from_header(authorization)
    if user is not None:
        return user.travelerId

    return traveler_id


def require_authenticated_user(
    authorization: str | None,
) -> AuthenticatedUser:
    user = authenticated_user_from_header(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")

    return user


def authenticated_user_from_header(
    authorization: str | None,
) -> AuthenticatedUser | None:
    access_token = bearer_token(authorization)
    if access_token is None:
        return None

    try:
        user = user_store.authenticate(access_token)
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=401, detail="Invalid account session.") from error

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid account session.")

    return user


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header.")

    return token.strip()


def save_trip_plan_history(
    request: TripPlanRequest,
    response: TripPlanResponse,
) -> None:
    try:
        history_store.save(request, response)
    except Exception:
        LOGGER.exception("Failed to persist completed trip plan.")
