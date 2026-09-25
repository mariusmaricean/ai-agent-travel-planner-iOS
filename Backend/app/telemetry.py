import json
import logging
from contextlib import contextmanager
from threading import get_ident
from typing import Any, Iterator

from app.runs import TripPlanRunStore
from app.tools import provider_logger

PROVIDER_EVENT_PREFIX = "provider_event "
TELEMETRY_STEP = "telemetry"


class ProviderTelemetryEventHandler(logging.Handler):
    def __init__(
        self,
        run_id: str,
        store: TripPlanRunStore,
        thread_id: int,
    ) -> None:
        super().__init__(level=logging.INFO)
        self.run_id = run_id
        self.store = store
        self.thread_id = thread_id

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread != self.thread_id:
            return

        try:
            payload = provider_event_payload(record)
            if payload is None:
                return

            self.store.emit(
                run_id=self.run_id,
                step=TELEMETRY_STEP,
                status="done",
                title=provider_event_title(payload),
                detail=provider_event_detail(payload),
            )
        except Exception:
            self.handleError(record)


@contextmanager
def capture_provider_telemetry(
    run_id: str,
    store: TripPlanRunStore,
) -> Iterator[None]:
    handler = ProviderTelemetryEventHandler(
        run_id=run_id,
        store=store,
        thread_id=get_ident(),
    )
    provider_logger.addHandler(handler)
    try:
        yield
    finally:
        provider_logger.removeHandler(handler)


def provider_event_payload(record: logging.LogRecord) -> dict[str, Any] | None:
    message = record.getMessage()
    if not message.startswith(PROVIDER_EVENT_PREFIX):
        return None

    try:
        payload = json.loads(message.removeprefix(PROVIDER_EVENT_PREFIX))
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    event = payload.get("event")
    return payload if isinstance(event, str) and event else None


def provider_event_title(payload: dict[str, Any]) -> str:
    event = payload["event"]
    titles = {
        "flight.amadeus_offers": "Amadeus flight offers",
        "flight.mock_fallback": "Flight provider fallback",
        "flight.provider_failure": "Flight provider failure",
        "location.amadeus_lookup": "Amadeus location lookup",
        "location.cache_hit": "Location cache hit",
        "location.cache_store": "Location cache stored",
        "location.iata_input": "IATA input accepted",
        "location.local_alias": "Location alias used",
        "location.provider_failure": "Location provider failure",
        "research.open_meteo_forecast": "Weather forecast added",
        "research.open_meteo_geocode": "Weather location found",
        "research.provider_failure": "Research provider fallback",
        "research.ticketmaster_events": "Event provider results",
    }
    return titles.get(event, "Provider telemetry")


def provider_event_detail(payload: dict[str, Any]) -> str:
    details = [
        f"{key.replace('_', ' ')}: {payload[key]}"
        for key in sorted(payload)
        if key != "event"
    ]
    return "; ".join(details) or payload["event"]
