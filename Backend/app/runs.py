from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.schemas import AgentRunEvent, TripPlanResponse, TripPlanRunSnapshot


class TripPlanRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, TripPlanRunSnapshot] = {}
        self._lock = Lock()

    def create(self) -> TripPlanRunSnapshot:
        run_id = str(uuid4())
        snapshot = TripPlanRunSnapshot(runId=run_id, status="running")

        with self._lock:
            self._runs[run_id] = snapshot

        return snapshot.model_copy(deep=True)

    def snapshot(self, run_id: str) -> TripPlanRunSnapshot | None:
        with self._lock:
            snapshot = self._runs.get(run_id)
            if snapshot is None:
                return None

            return snapshot.model_copy(deep=True)

    def emit(
        self,
        run_id: str,
        step: str,
        status: str,
        title: str,
        detail: str = "",
    ) -> AgentRunEvent | None:
        with self._lock:
            snapshot = self._runs.get(run_id)
            if snapshot is None:
                return None

            event = AgentRunEvent(
                id=len(snapshot.events) + 1,
                step=step,
                status=status,
                title=title,
                detail=detail,
                createdAt=datetime.now(timezone.utc),
            )
            snapshot.events.append(event)
            return event

    def complete(self, run_id: str, result: TripPlanResponse) -> None:
        with self._lock:
            snapshot = self._runs.get(run_id)
            if snapshot is None:
                return

            snapshot.status = "completed"
            snapshot.result = result

    def fail(self, run_id: str, message: str) -> None:
        with self._lock:
            snapshot = self._runs.get(run_id)
            if snapshot is None:
                return

            step, title = self._failure_target(snapshot)
            event = AgentRunEvent(
                id=len(snapshot.events) + 1,
                step=step,
                status="failed",
                title=title,
                detail=message,
                createdAt=datetime.now(timezone.utc),
            )
            snapshot.events.append(event)
            snapshot.status = "failed"
            snapshot.error = message

    def _failure_target(self, snapshot: TripPlanRunSnapshot) -> tuple[str, str]:
        for event in reversed(snapshot.events):
            if event.status == "active":
                return event.step, event.title

        return "run", "Agent run"
