import logging
import os
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event

from app.history import TripPlanHistoryStore
from app.job_queue import TripPlanJobQueue
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
        queue: TripPlanJobQueue | None = None,
        poll_interval_seconds: float = 0.25,
    ) -> None:
        self.store = store
        self.history_store = history_store
        self.queue = queue
        self._stop_event = Event()
        self._poll_interval_seconds = max(0.01, poll_interval_seconds)
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, max_workers),
            thread_name_prefix="trip-plan-run",
        )
        self._worker_futures: list[Future[None]] = []
        if self.queue is not None:
            for _ in range(max(1, max_workers)):
                self._worker_futures.append(self._executor.submit(self._work_loop))

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

        queue = TripPlanJobQueue.from_environment() if durable_job_queue_enabled() else None
        return cls(
            store=store,
            history_store=history_store,
            max_workers=max_workers,
            queue=queue,
        )

    def submit(
        self,
        run_id: str,
        request: TripPlanRequest,
    ) -> Future[TripPlanResponse | None] | None:
        if self.queue is not None:
            self.queue.enqueue(run_id, request)
            return None

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
            if self.queue is not None:
                self.queue.complete(run_id)
            return result
        except Exception as error:
            self.store.fail(run_id, str(error))
            if self.queue is not None:
                self.queue.fail(run_id, str(error))
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
        self._stop_event.set()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _work_loop(self) -> None:
        while not self._stop_event.is_set():
            if self.queue is None:
                return

            record = self.queue.next_job()
            if record is None:
                self._stop_event.wait(self._poll_interval_seconds)
                continue

            self.run(record.runId, record.request)


def durable_job_queue_enabled() -> bool:
    value = os.environ.get("TRIP_PLAN_JOB_QUEUE_ENABLED", "true").strip().lower()
    return value not in ("0", "false", "no", "off")
