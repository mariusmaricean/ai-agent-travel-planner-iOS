import os
from concurrent.futures import Future, ThreadPoolExecutor

from app.planner import create_trip_plan
from app.runs import TripPlanRunStore
from app.schemas import TripPlanRequest, TripPlanResponse


class TripPlanJobRunner:
    def __init__(self, store: TripPlanRunStore, max_workers: int = 2) -> None:
        self.store = store
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, max_workers),
            thread_name_prefix="trip-plan-run",
        )

    @classmethod
    def from_environment(cls, store: TripPlanRunStore) -> "TripPlanJobRunner":
        try:
            max_workers = int(os.environ.get("TRIP_PLAN_RUN_WORKERS", "2"))
        except ValueError:
            max_workers = 2

        return cls(store=store, max_workers=max_workers)

    def submit(self, run_id: str, request: TripPlanRequest) -> Future[TripPlanResponse | None]:
        return self._executor.submit(self.run, run_id, request)

    def run(self, run_id: str, request: TripPlanRequest) -> TripPlanResponse | None:
        try:
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
            self.store.complete(run_id, result)
            return result
        except Exception as error:
            self.store.fail(run_id, str(error))
            return None

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
