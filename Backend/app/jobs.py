import logging
import os
from concurrent.futures import Future, ThreadPoolExecutor

from app.history import TripPlanHistoryStore
from app.planner import create_trip_plan
from app.runs import TripPlanRunStore
from app.schemas import TripPlanRequest, TripPlanResponse
from app.telemetry import capture_provider_telemetry

LOGGER = logging.getLogger(__name__)


class TripPlanJobRunner:
    def __init__(
        self,
        store: TripPlanRunStore,
        history_store: TripPlanHistoryStore | None = None,
        max_workers: int = 2,
    ) -> None:
        self.store = store
        self.history_store = history_store
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, max_workers),
            thread_name_prefix="trip-plan-run",
        )

    @classmethod
    def from_environment(
        cls,
        store: TripPlanRunStore,
        history_store: TripPlanHistoryStore | None = None,
    ) -> "TripPlanJobRunner":
        try:
            max_workers = int(os.environ.get("TRIP_PLAN_RUN_WORKERS", "2"))
        except ValueError:
            max_workers = 2

        return cls(store=store, history_store=history_store, max_workers=max_workers)

    def submit(self, run_id: str, request: TripPlanRequest) -> Future[TripPlanResponse | None]:
        return self._executor.submit(self.run, run_id, request)

    def run(self, run_id: str, request: TripPlanRequest) -> TripPlanResponse | None:
        try:
            with capture_provider_telemetry(run_id, self.store):
                result = create_trip_plan(
                    request,
                    progress=lambda step, status, title, detail: self.store.emit(
                        run_id=run_id,
                        step=step,
                        status=status,
                        title=title,
                        detail=detail,
                    ),
                )
            self.save_history(request, result, run_id)
            self.store.complete(run_id, result)
            return result
        except Exception as error:
            self.store.fail(run_id, str(error))
            return None

    def save_history(
        self,
        request: TripPlanRequest,
        response: TripPlanResponse,
        run_id: str,
    ) -> None:
        if self.history_store is None:
            return

        try:
            self.history_store.save(request, response, run_id=run_id)
        except Exception:
            LOGGER.exception("Failed to persist completed trip plan.")

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
