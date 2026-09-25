import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.schemas import MemoryNote, SavedTripPlan, TripPlanRequest, TripPlanResponse

DEFAULT_TRAVELER_ID = "local"


class TripPlanHistoryStore:
    def __init__(self, path: str | Path | None = None, max_entries: int = 100) -> None:
        self._path = Path(path) if path is not None else None
        self._max_entries = max(1, max_entries)
        self._records: list[SavedTripPlan] = []
        self._lock = Lock()
        self._load()

    @classmethod
    def from_environment(cls) -> "TripPlanHistoryStore":
        path = history_store_path()
        try:
            max_entries = int(os.environ.get("TRIP_PLAN_HISTORY_LIMIT", "100"))
        except ValueError:
            max_entries = 100

        return cls(path=path, max_entries=max_entries)

    def save(
        self,
        request: TripPlanRequest,
        response: TripPlanResponse,
        run_id: str | None = None,
        traveler_id: str | None = None,
    ) -> SavedTripPlan:
        normalized_traveler_id = normalize_traveler_id(
            traveler_id or request.travelerId
        )
        normalized_request = request.model_copy(
            update={"travelerId": normalized_traveler_id}
        )
        record = SavedTripPlan(
            id=str(uuid4()),
            travelerId=normalized_traveler_id,
            request=normalized_request,
            response=response,
            createdAt=datetime.now(timezone.utc),
            runId=run_id,
        )

        with self._lock:
            self._records.append(record)
            self._records = self._records[-self._max_entries :]
            self._persist_locked()

        return record.model_copy(deep=True)

    def recent(
        self,
        limit: int = 20,
        traveler_id: str | None = None,
    ) -> list[SavedTripPlan]:
        normalized_limit = max(1, limit)
        normalized_traveler_id = normalize_traveler_id(traveler_id)
        with self._lock:
            traveler_records = [
                record
                for record in self._records
                if record.travelerId == normalized_traveler_id
            ]
            records = list(reversed(traveler_records[-normalized_limit:]))
            return [record.model_copy(deep=True) for record in records]

    def get(
        self,
        plan_id: str,
        traveler_id: str | None = None,
    ) -> SavedTripPlan | None:
        normalized_traveler_id = normalize_traveler_id(traveler_id)
        with self._lock:
            for record in self._records:
                if (
                    record.id == plan_id
                    and record.travelerId == normalized_traveler_id
                ):
                    return record.model_copy(deep=True)

        return None

    def latest_memory(self, traveler_id: str | None = None) -> list[MemoryNote]:
        normalized_traveler_id = normalize_traveler_id(traveler_id)
        with self._lock:
            for record in reversed(self._records):
                if (
                    record.travelerId == normalized_traveler_id
                    and record.response.memory is not None
                ):
                    return [note.model_copy(deep=True) for note in record.response.memory]

        return []

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        records = payload.get("records", []) if isinstance(payload, dict) else []
        if not isinstance(records, list):
            return

        loaded: list[SavedTripPlan] = []
        for record_payload in records:
            if not isinstance(record_payload, dict):
                continue

            try:
                loaded.append(SavedTripPlan.model_validate(record_payload))
            except ValueError:
                continue

        self._records = loaded[-self._max_entries :]

    def _persist_locked(self) -> None:
        if self._path is None:
            return

        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "records": [record.model_dump(mode="json") for record in self._records]
        }
        temporary_path = self._path.with_name(f"{self._path.name}.tmp")
        temporary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary_path.replace(self._path)


def history_store_path() -> Path:
    configured_path = os.environ.get("TRIP_PLAN_HISTORY_STORE_PATH", "").strip()
    if configured_path:
        path = Path(configured_path)
        if not path.is_absolute():
            path = backend_directory() / path

        return path

    return backend_directory() / ".data" / "trip_plan_history.json"


def normalize_traveler_id(traveler_id: str | None) -> str:
    normalized = (traveler_id or "").strip()
    if normalized:
        return normalized

    return DEFAULT_TRAVELER_ID


def backend_directory() -> Path:
    return Path(__file__).resolve().parents[1]
