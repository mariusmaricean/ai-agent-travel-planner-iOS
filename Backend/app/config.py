import os
from typing import Any


def backend_configuration_status() -> dict[str, Any]:
    warnings = configuration_warnings()
    return {
        "status": "warning" if warnings else "ok",
        "warnings": warnings,
        "providers": {
            "flight": os.environ.get("FLIGHT_PROVIDER", "mock").strip() or "mock",
            "destinationResearch": destination_research_provider_names(),
            "durableJobQueue": durable_job_queue_enabled(),
            "modelBackedPlanning": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        },
    }


def configuration_warnings() -> list[str]:
    warnings: list[str] = []

    if flight_provider_name() == "amadeus" and missing_amadeus_credentials():
        warnings.append("FLIGHT_PROVIDER=amadeus requires Amadeus credentials.")

    providers = destination_research_provider_names()
    if includes_provider(providers, "ticketmaster") and not os.environ.get(
        "TICKETMASTER_API_KEY",
        "",
    ).strip():
        warnings.append("Ticketmaster research requires TICKETMASTER_API_KEY.")

    if includes_provider(providers, "osm_places") and not os.environ.get(
        "OSM_USER_AGENT",
        "",
    ).strip():
        warnings.append("OpenStreetMap place research should set OSM_USER_AGENT.")

    numeric_settings = [
        ("TRIP_PLAN_RUN_WORKERS", 1),
        ("TRIP_PLAN_HISTORY_LIMIT", 1),
        ("OPENAI_TIMEOUT_SECONDS", 1),
        ("AMADEUS_TIMEOUT_SECONDS", 1),
        ("OPEN_METEO_TIMEOUT_SECONDS", 1),
        ("TICKETMASTER_TIMEOUT_SECONDS", 1),
        ("OSM_TIMEOUT_SECONDS", 1),
        ("OSM_MAX_PLACES", 1),
    ]
    for key, minimum in numeric_settings:
        warning = numeric_environment_warning(key, minimum)
        if warning is not None:
            warnings.append(warning)

    return warnings


def flight_provider_name() -> str:
    return os.environ.get("FLIGHT_PROVIDER", "mock").strip().lower() or "mock"


def destination_research_provider_names() -> list[str]:
    configured = os.environ.get("DESTINATION_RESEARCH_PROVIDER", "mock").strip().lower()
    if configured in ("", "mock"):
        return []

    names = [
        name.strip()
        for name in configured.replace(";", ",").split(",")
        if name.strip()
    ]
    if names == ["all"]:
        return ["open_meteo", "ticketmaster", "osm_places", "local_transport", "budget"]
    if names == ["real"]:
        return ["open_meteo", "ticketmaster", "osm_places"]

    return names


def includes_provider(providers: list[str], provider_name: str) -> bool:
    aliases = {
        "ticketmaster": {"ticketmaster", "ticketmaster_events", "events"},
        "osm_places": {"osm", "osm_places", "openstreetmap", "places"},
    }
    allowed_names = aliases.get(provider_name, {provider_name})
    return any(provider in allowed_names for provider in providers)


def missing_amadeus_credentials() -> bool:
    return not (
        os.environ.get("AMADEUS_CLIENT_ID", "").strip()
        and os.environ.get("AMADEUS_CLIENT_SECRET", "").strip()
    )


def durable_job_queue_enabled() -> bool:
    value = os.environ.get("TRIP_PLAN_JOB_QUEUE_ENABLED", "true").strip().lower()
    return value not in ("0", "false", "no", "off")


def numeric_environment_warning(key: str, minimum: float) -> str | None:
    value = os.environ.get(key, "").strip()
    if not value:
        return None

    try:
        numeric_value = float(value)
    except ValueError:
        return f"{key} must be numeric."

    if numeric_value < minimum:
        return f"{key} must be at least {minimum:g}."

    return None
