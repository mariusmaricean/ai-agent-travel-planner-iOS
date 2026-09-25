import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from app.schemas import TripPlanJobRecord, TripPlanRequest


class TripPlanJobQueue:
    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._jobs: dict[str, TripPlanJobRecord] = {}
        self._lock = Lock()
        self._load()

    @classmethod
    def from_environment(cls) -> "TripPlanJobQueue":
        return cls(path=job_queue_path())

    def enqueue(self, run_id: str, request: TripPlanRequest) -> TripPlanJobRecord:
        now = datetime.now(timezone.utc)
        record = TripPlanJobRecord(
            runId=run_id,
            request=request,
            status="queued",
            attempts=0,
            createdAt=now,
            updatedAt=now,
        )

        with self._lock:
            self._jobs[run_id] = record
            self._persist_locked()

        return record.model_copy(deep=True)

    def next_job(self) -> TripPlanJobRecord | None:
        with self._lock:
            queued_jobs = sorted(
                (
                    job
                    for job in self._jobs.values()
                    if job.status == "queued"
                ),
                key=lambda job: job.createdAt,
            )
            if not queued_jobs:
                return None

            record = queued_jobs[0]
            updated = record.model_copy(
                update={
                    "status": "running",
                    "attempts": record.attempts + 1,
                    "updatedAt": datetime.now(timezone.utc),
                    "lastError": None,
                }
            )
            self._jobs[updated.runId] = updated
            self._persist_locked()
            return updated.model_copy(deep=True)

    def complete(self, run_id: str) -> None:
        self._update_status(run_id, status="completed", error=None)

    def fail(self, run_id: str, error: str) -> None:
        self._update_status(run_id, status="failed", error=error)

    def get(self, run_id: str) -> TripPlanJobRecord | None:
        with self._lock:
            record = self._jobs.get(run_id)
            if record is None:
                return None

            return record.model_copy(deep=True)

    def _update_status(
        self,
        run_id: str,
        status: str,
        error: str | None,
    ) -> None:
        with self._lock:
            record = self._jobs.get(run_id)
            if record is None:
                return

            self._jobs[run_id] = record.model_copy(
                update={
                    "status": status,
                    "updatedAt": datetime.now(timezone.utc),
                    "lastError": error,
                }
            )
            self._persist_locked()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        if not isinstance(jobs, list):
            return

        recovered_any = False
        for job_payload in jobs:
            if not isinstance(job_payload, dict):
                continue

            try:
                record = TripPlanJobRecord.model_validate(job_payload)
            except ValueError:
                continue

            if record.status == "running":
                record = record.model_copy(
                    update={
                        "status": "queued",
                        "updatedAt": datetime.now(timezone.utc),
                        "lastError": "Re-queued after backend restart.",
                    }
                )
                recovered_any = True

            self._jobs[record.runId] = record

        if recovered_any:
            self._persist_locked()

    def _persist_locked(self) -> None:
        if self._path is None:
            return

        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "jobs": [
                job.model_dump(mode="json")
                for job in sorted(self._jobs.values(), key=lambda item: item.createdAt)
            ]
        }
        temporary_path = self._path.with_name(f"{self._path.name}.tmp")
        temporary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary_path.replace(self._path)


def job_queue_path() -> Path:
    configured_path = os.environ.get("TRIP_PLAN_JOB_QUEUE_PATH", "").strip()
    if configured_path:
        path = Path(configured_path)
        if not path.is_absolute():
            path = backend_directory() / path

        return path

    return backend_directory() / ".data" / "trip_plan_jobs.json"


def backend_directory() -> Path:
    return Path(__file__).resolve().parents[1]
