import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.schemas import AgentRunEvent, TripPlanResponse, TripPlanRunSnapshot

INTERRUPTED_RUN_MESSAGE = "Run was interrupted before completion."


class TripPlanRunStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._runs: dict[str, TripPlanRunSnapshot] = {}
        self._lock = Lock()
        self._load()

    @classmethod
    def from_environment(cls) -> "TripPlanRunStore":
        configured_path = os.environ.get("TRIP_PLAN_RUN_STORE_PATH", "").strip()
        if configured_path:
            path = Path(configured_path)
            if not path.is_absolute():
                path = Path(__file__).resolve().parents[1] / path

            return cls(path=path)

        return cls(path=Path(__file__).resolve().parents[1] / ".data" / "trip_plan_runs.json")

    def create(self) -> TripPlanRunSnapshot:
        run_id = str(uuid4())
        snapshot = TripPlanRunSnapshot(runId=run_id, status="running")

        with self._lock:
            self._runs[run_id] = snapshot
            self._persist_locked()

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
            self._persist_locked()
            return event

    def complete(self, run_id: str, result: TripPlanResponse) -> None:
        with self._lock:
            snapshot = self._runs.get(run_id)
            if snapshot is None:
                return

            snapshot.status = "completed"
            snapshot.result = result
            self._persist_locked()

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
            self._persist_locked()

    def _failure_target(self, snapshot: TripPlanRunSnapshot) -> tuple[str, str]:
        for event in reversed(snapshot.events):
            if event.status == "active":
                return event.step, event.title

        return "run", "Agent run"

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        runs = payload.get("runs", []) if isinstance(payload, dict) else []
        if not isinstance(runs, list):
            return

        recovered_any = False
        for run_payload in runs:
            if not isinstance(run_payload, dict):
                continue

            try:
                snapshot = TripPlanRunSnapshot.model_validate(run_payload)
            except ValueError:
                continue

            if snapshot.status == "running":
                snapshot = self._interrupted_snapshot(snapshot)
                recovered_any = True

            self._runs[snapshot.runId] = snapshot

        if recovered_any:
            self._persist_locked()

    def _interrupted_snapshot(self, snapshot: TripPlanRunSnapshot) -> TripPlanRunSnapshot:
        recovered = snapshot.model_copy(deep=True)
        step, title = self._failure_target(recovered)
        recovered.events.append(
            AgentRunEvent(
                id=len(recovered.events) + 1,
                step=step,
                status="failed",
                title=title,
                detail=INTERRUPTED_RUN_MESSAGE,
                createdAt=datetime.now(timezone.utc),
            )
        )
        recovered.status = "failed"
        recovered.error = INTERRUPTED_RUN_MESSAGE
        return recovered

    def _persist_locked(self) -> None:
        if self._path is None:
            return

        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "runs": [
                snapshot.model_dump(mode="json")
                for snapshot in sorted(self._runs.values(), key=lambda run: run.runId)
            ]
        }
        temporary_path = self._path.with_name(f"{self._path.name}.tmp")
        temporary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary_path.replace(self._path)
