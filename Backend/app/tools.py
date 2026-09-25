import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Any, Callable, Optional

from dotenv import load_dotenv

from app.schemas import DestinationResearch, MemoryNote, TripDay, TripOption, TripPlanRequest

load_dotenv()

PROVIDER_LOGGER_NAME = "travel_planner.providers"
provider_logger = logging.getLogger(PROVIDER_LOGGER_NAME)
provider_logger.setLevel(
    getattr(logging, os.environ.get("PROVIDER_LOG_LEVEL", "INFO").upper(), logging.INFO)
)


@dataclass(frozen=True)
class FareOption:
    name: str
    fare: float
    score: int
    meta: str


@dataclass(frozen=True)
class FlightSearchQuery:
    origin: str
    destination: str
    depart_date: datetime
    return_date: datetime
    budget: float


@dataclass(frozen=True)
class ResolvedLocation:
    query: str
    code: str
    name: str
    source: str


@dataclass(frozen=True)
class DestinationResearchQuery:
    origin: str
    destination: str
    depart_date: datetime
    return_date: datetime
    budget: float
    mood: str
    constraints: str
    memory: list[MemoryNote]


@dataclass(frozen=True)
class ItineraryPlanningInput:
    origin: str
    destination: str
    depart_date: datetime
    return_date: datetime
    budget: float
    duration: int
    mood: str
    constraints: str
    memory: list[MemoryNote]
    fares: list[FareOption]
    destination_research: Optional[DestinationResearch] = None


@dataclass(frozen=True)
class ItineraryRevisionInput:
    request: TripPlanRequest
    original_trip: TripOption
    critic_score: int
    issues: list[str]
    recommendations: list[str]
    destination_research: Optional[DestinationResearch] = None


FlightProviderFunction = Callable[[FlightSearchQuery], list[FareOption]]
LocationResolverFunction = Callable[[str], Optional[ResolvedLocation]]
DestinationResearchFunction = Callable[[DestinationResearchQuery], DestinationResearch]
ItineraryPlannerFunction = Callable[[ItineraryPlanningInput], list[TripOption]]
ItineraryReviserFunction = Callable[[ItineraryRevisionInput], TripOption]


@dataclass(frozen=True)
class TravelPlanningToolRouter:
    flight_provider: FlightProviderFunction
    itinerary_planner: ItineraryPlannerFunction
    location_resolver: Optional[LocationResolverFunction] = None
    destination_researcher: Optional[DestinationResearchFunction] = None
    itinerary_reviser: Optional[ItineraryReviserFunction] = None

    def search_flights(self, request: TripPlanRequest) -> list[FareOption]:
        origin = self.resolve_location_code(request.origin)
        destination = self.resolve_location_code(request.destination)
        query = FlightSearchQuery(
            origin=origin,
            destination=destination,
            depart_date=request.departDate,
            return_date=request.returnDate,
            budget=request.budget,
        )
        return self.flight_provider(query)

    def resolve_location_code(self, value: str) -> str:
        if self.location_resolver is None:
            return value

        resolved = self.location_resolver(value)
        return resolved.code if resolved is not None else value

    def research_destination(self, request: TripPlanRequest) -> DestinationResearch:
        query = DestinationResearchQuery(
            origin=request.origin,
            destination=request.destination,
            depart_date=request.departDate,
            return_date=request.returnDate,
            budget=request.budget,
            mood=request.mood,
            constraints=request.constraints,
            memory=request.memory,
        )
        researcher = self.destination_researcher or model_backed_destination_researcher
        return researcher(query)

    def build_itinerary(
        self,
        request: TripPlanRequest,
        fares: list[FareOption],
        destination_research: Optional[DestinationResearch] = None,
    ) -> list[TripOption]:
        planning_input = ItineraryPlanningInput(
            origin=request.origin,
            destination=request.destination,
            depart_date=request.departDate,
            return_date=request.returnDate,
            budget=request.budget,
            duration=trip_duration(request),
            mood=request.mood,
            constraints=request.constraints,
            memory=request.memory,
            fares=fares,
            destination_research=destination_research,
        )
        return self.itinerary_planner(planning_input)

    def revise_itinerary(
        self,
        request: TripPlanRequest,
        trip: TripOption,
        critic_score: int,
        issues: list[str],
        recommendations: list[str],
        destination_research: Optional[DestinationResearch] = None,
    ) -> TripOption:
        revision_input = ItineraryRevisionInput(
            request=request,
            original_trip=trip,
            critic_score=critic_score,
            issues=issues,
            recommendations=recommendations,
            destination_research=destination_research,
        )
        reviser = self.itinerary_reviser or model_backed_itinerary_reviser
        return reviser(revision_input)


class LocationResolutionCache:
    def __init__(self, max_entries: int = 128) -> None:
        self.max_entries = max(1, max_entries)
        self._locations: OrderedDict[str, ResolvedLocation] = OrderedDict()
        self._lock = RLock()

    def get(self, value: str) -> Optional[ResolvedLocation]:
        key = normalized_location_name(value)
        if not key:
            return None

        with self._lock:
            location = self._locations.pop(key, None)
            if location is None:
                return None

            self._locations[key] = location
            return location

    def set(self, value: str, location: ResolvedLocation) -> None:
        key = normalized_location_name(value)
        if not key:
            return

        with self._lock:
            self._locations.pop(key, None)
            self._locations[key] = location
            while len(self._locations) > self.max_entries:
                self._locations.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._locations.clear()


def mock_flight_provider(query: FlightSearchQuery) -> list[FareOption]:
    base_fare = max(320, round(query.budget * 0.42))
    duration = trip_duration_from_dates(query.depart_date, query.return_date)

    return [
        FareOption(
            name="Balanced Sprint",
            fare=base_fare + 70,
            score=94,
            meta=f"{duration} days | morning outbound | 1 checked bag | source: mock",
        ),
        FareOption(
            name="Lowest Fare",
            fare=base_fare - 45,
            score=88,
            meta=f"{duration} days | one connection | budget winner | source: mock",
        ),
        FareOption(
            name="Comfort Pick",
            fare=base_fare + 180,
            score=91,
            meta=f"{duration} days | direct flight | aisle-friendly timing | source: mock",
        ),
    ]


class FlightProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class AmadeusFlightProviderConfig:
    client_id: str
    client_secret: str
    base_url: str = "https://test.api.amadeus.com"
    timeout_seconds: float = 20
    currency_code: str = "USD"
    max_offers: int = 3
    adults: int = 1

    @classmethod
    def from_environment(cls) -> Optional["AmadeusFlightProviderConfig"]:
        client_id = os.environ.get("AMADEUS_CLIENT_ID", "").strip()
        client_secret = os.environ.get("AMADEUS_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            return None

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            base_url=os.environ.get("AMADEUS_BASE_URL", "https://test.api.amadeus.com").strip()
            or "https://test.api.amadeus.com",
            timeout_seconds=float(os.environ.get("AMADEUS_TIMEOUT_SECONDS", "20")),
            currency_code=os.environ.get("AMADEUS_CURRENCY_CODE", "USD").strip() or "USD",
            max_offers=int(os.environ.get("AMADEUS_MAX_OFFERS", "3")),
            adults=int(os.environ.get("AMADEUS_ADULTS", "1")),
        )


@dataclass(frozen=True)
class AmadeusFlightProvider:
    config: AmadeusFlightProviderConfig

    @classmethod
    def from_environment(cls) -> Optional["AmadeusFlightProvider"]:
        config = AmadeusFlightProviderConfig.from_environment()
        if config is None:
            return None

        return cls(config=config)

    def search(self, query: FlightSearchQuery) -> list[FareOption]:
        token: str | None = None
        origin = local_resolved_location(query.origin)
        destination = local_resolved_location(query.destination)

        if origin is None or destination is None:
            token = self.access_token()

        if origin is None and token is not None:
            origin = self.remote_resolved_location(query.origin, token)

        if destination is None and token is not None:
            destination = self.remote_resolved_location(query.destination, token)

        if origin is None or destination is None:
            raise FlightProviderError("Amadeus searches require city or airport IATA codes.")

        token = token or self.access_token()
        payload = self.flight_offers(query, origin.code, destination.code, token)
        fares = amadeus_fare_options(payload, self.config.currency_code)
        if not fares:
            raise FlightProviderError("Amadeus returned no flight offers.")

        log_provider_event(
            "flight.amadeus_offers",
            origin=origin.code,
            destination=destination.code,
            offer_count=len(fares),
        )
        return fares

    def resolve_location(self, value: str) -> Optional[ResolvedLocation]:
        local_location = local_resolved_location(value)
        if local_location is not None:
            return local_location

        token = self.access_token()
        return self.remote_resolved_location(value, token)

    def remote_resolved_location(
        self,
        value: str,
        token: str,
    ) -> Optional[ResolvedLocation]:
        keyword = amadeus_location_keyword(value)
        if keyword is None:
            log_provider_event(
                "location.amadeus_lookup",
                query=value,
                result="skipped",
            )
            return None

        params = urllib.parse.urlencode(
            {
                "subType": "CITY,AIRPORT",
                "keyword": keyword,
                "page[limit]": 1,
            }
        )
        request = urllib.request.Request(
            url=f"{self.config.base_url.rstrip('/')}/v1/reference-data/locations?{params}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            method="GET",
        )
        payload = json_response(request, self.config.timeout_seconds, "Amadeus location search")
        location = amadeus_resolved_location(payload, value)
        log_provider_event(
            "location.amadeus_lookup",
            code=location.code if location is not None else None,
            keyword=keyword,
            query=value,
            result="hit" if location is not None else "miss",
        )
        return location

    def access_token(self) -> str:
        body = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url=f"{self.config.base_url.rstrip('/')}/v1/security/oauth2/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        payload = json_response(request, self.config.timeout_seconds, "Amadeus token request")
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise FlightProviderError("Amadeus token response did not include an access token.")

        return token

    def flight_offers(
        self,
        query: FlightSearchQuery,
        origin: str,
        destination: str,
        token: str,
    ) -> dict[str, Any]:
        params = urllib.parse.urlencode(
            {
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": query.depart_date.date().isoformat(),
                "returnDate": query.return_date.date().isoformat(),
                "adults": self.config.adults,
                "currencyCode": self.config.currency_code,
                "max": self.config.max_offers,
            }
        )
        request = urllib.request.Request(
            url=f"{self.config.base_url.rstrip('/')}/v2/shopping/flight-offers?{params}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            method="GET",
        )
        return json_response(request, self.config.timeout_seconds, "Amadeus flight offers request")


def configured_flight_provider(query: FlightSearchQuery) -> list[FareOption]:
    provider_name = os.environ.get("FLIGHT_PROVIDER", "").strip().lower()
    if provider_name == "mock":
        log_provider_event(
            "flight.mock_fallback",
            origin=query.origin,
            destination=query.destination,
            reason="configured_mock",
        )
        return mock_flight_provider(query)

    provider = AmadeusFlightProvider.from_environment()

    if provider is None:
        log_provider_event(
            "flight.mock_fallback",
            origin=query.origin,
            destination=query.destination,
            reason="missing_amadeus_credentials",
        )
        return mock_flight_provider(query)

    try:
        return provider.search(query)
    except FlightProviderError as error:
        log_provider_event(
            "flight.provider_failure",
            origin=query.origin,
            destination=query.destination,
            provider="amadeus",
            error=str(error),
        )
        log_provider_event(
            "flight.mock_fallback",
            origin=query.origin,
            destination=query.destination,
            reason="provider_failure",
        )
        return mock_flight_provider(query)


def configured_location_resolver(value: str) -> Optional[ResolvedLocation]:
    local_location = local_resolved_location(value)
    if local_location is not None:
        return local_location

    provider_name = os.environ.get("FLIGHT_PROVIDER", "").strip().lower()
    if provider_name == "mock":
        return None

    provider = AmadeusFlightProvider.from_environment()
    if provider is None:
        return None

    try:
        return provider.resolve_location(value)
    except FlightProviderError as error:
        log_provider_event(
            "location.provider_failure",
            provider="amadeus",
            query=value,
            error=str(error),
        )
        return None


def cached_location(
    value: str,
    cache: LocationResolutionCache,
    resolver: LocationResolverFunction,
) -> Optional[ResolvedLocation]:
    cached = cache.get(value)
    if cached is not None:
        log_provider_event(
            "location.cache_hit",
            code=cached.code,
            query=value,
            source=cached.source,
        )
        return cached

    resolved = resolver(value)
    if resolved is not None:
        cache.set(value, resolved)
        log_provider_event(
            "location.cache_store",
            code=resolved.code,
            query=value,
            source=resolved.source,
        )

    return resolved


def cached_location_resolver(value: str) -> Optional[ResolvedLocation]:
    return cached_location(value, location_resolution_cache, configured_location_resolver)


def resolve_location(value: str) -> Optional[ResolvedLocation]:
    return cached_location_resolver(value)


def location_cache_max_entries() -> int:
    try:
        return int(os.environ.get("LOCATION_CACHE_MAX_ENTRIES", "128"))
    except ValueError:
        return 128


location_resolution_cache = LocationResolutionCache(max_entries=location_cache_max_entries())


def log_provider_event(event: str, **details: Any) -> None:
    payload = {
        "event": event,
        **{key: value for key, value in details.items() if value is not None},
    }
    provider_logger.info("provider_event %s", json.dumps(payload, sort_keys=True, default=str))


def json_response(
    request: urllib.request.Request,
    timeout_seconds: float,
    context: str,
) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise FlightProviderError(
            f"{context} failed with status {error.code}: {error_body}"
        ) from error
    except urllib.error.URLError as error:
        raise FlightProviderError(f"{context} failed: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise FlightProviderError(f"{context} returned invalid JSON.") from error

    if not isinstance(payload, dict):
        raise FlightProviderError(f"{context} did not return an object payload.")

    return payload


def amadeus_resolved_location(
    payload: dict[str, Any],
    query: str,
) -> Optional[ResolvedLocation]:
    locations = payload.get("data", [])
    if not isinstance(locations, list):
        raise FlightProviderError("Amadeus location response did not include a data array.")

    for location in locations:
        if not isinstance(location, dict):
            continue

        code = location.get("iataCode")
        if not isinstance(code, str) or len(code.strip()) != 3:
            continue

        name = location.get("name")
        return ResolvedLocation(
            query=query,
            code=code.strip().upper(),
            name=name if isinstance(name, str) and name else code.strip().upper(),
            source="Amadeus Location Search",
        )

    return None


def amadeus_fare_options(payload: dict[str, Any], currency_code: str) -> list[FareOption]:
    offers = payload.get("data", [])
    if not isinstance(offers, list):
        raise FlightProviderError("Amadeus flight offers response did not include a data array.")

    fares: list[FareOption] = []
    for index, offer in enumerate(offers):
        if not isinstance(offer, dict):
            continue

        fare = amadeus_offer_price(offer)
        if fare is None:
            continue

        fares.append(
            FareOption(
                name=f"Amadeus Offer {index + 1}",
                fare=fare,
                score=amadeus_offer_score(offer, index),
                meta=amadeus_offer_meta(offer, currency_code),
            )
        )

    return fares


def amadeus_offer_price(offer: dict[str, Any]) -> Optional[float]:
    price = offer.get("price", {})
    if not isinstance(price, dict):
        return None

    total = price.get("grandTotal") or price.get("total")
    try:
        return float(total)
    except (TypeError, ValueError):
        return None


def amadeus_offer_score(offer: dict[str, Any], index: int) -> int:
    return max(70, 96 - (amadeus_connection_count(offer) * 4) - (index * 2))


def amadeus_offer_meta(offer: dict[str, Any], currency_code: str) -> str:
    carriers = amadeus_carrier_codes(offer)
    carrier_detail = "/".join(carriers[:2]) if carriers else "carrier pending"
    connection_count = amadeus_connection_count(offer)
    connection_detail = "nonstop" if connection_count == 0 else f"{connection_count} connection"
    if connection_count > 1:
        connection_detail = f"{connection_count} connections"

    return f"source: Amadeus | {carrier_detail} | {connection_detail} | {currency_code}"


def amadeus_connection_count(offer: dict[str, Any]) -> int:
    itineraries = offer.get("itineraries", [])
    if not isinstance(itineraries, list) or not itineraries:
        return 0

    segment_count = 0
    for itinerary in itineraries:
        if not isinstance(itinerary, dict):
            continue

        segments = itinerary.get("segments", [])
        if isinstance(segments, list):
            segment_count += len(segments)

    return max(0, segment_count - len(itineraries))


def amadeus_carrier_codes(offer: dict[str, Any]) -> list[str]:
    carriers: list[str] = []
    itineraries = offer.get("itineraries", [])
    if not isinstance(itineraries, list):
        return carriers

    for itinerary in itineraries:
        if not isinstance(itinerary, dict):
            continue

        segments = itinerary.get("segments", [])
        if not isinstance(segments, list):
            continue

        for segment in segments:
            if not isinstance(segment, dict):
                continue

            carrier = segment.get("carrierCode")
            if isinstance(carrier, str) and carrier not in carriers:
                carriers.append(carrier)

    return carriers


def iata_location_code(value: str) -> Optional[str]:
    location = local_resolved_location(value)
    return location.code if location is not None else None


def local_resolved_location(value: str) -> Optional[ResolvedLocation]:
    stripped = value.strip().upper()
    if len(stripped) == 3 and stripped.isalpha():
        log_provider_event(
            "location.iata_input",
            code=stripped,
            query=value,
        )
        return ResolvedLocation(
            query=value,
            code=stripped,
            name=stripped,
            source="IATA input",
        )

    code = IATA_LOCATION_ALIASES.get(normalized_location_name(value))
    if code is None:
        return None

    log_provider_event(
        "location.local_alias",
        code=code,
        query=value,
    )
    return ResolvedLocation(
        query=value,
        code=code,
        name=value.strip() or code,
        source="local alias",
    )


def amadeus_location_keyword(value: str) -> Optional[str]:
    normalized = normalized_location_name(value)
    if not normalized:
        return None

    first_word = normalized.split()[0]
    if len(first_word) < 2:
        return None

    return first_word[:10].upper()


def normalized_location_name(value: str) -> str:
    return " ".join(
        value.lower()
        .replace("-", " ")
        .replace("_", " ")
        .replace(",", " ")
        .split()
    )


IATA_LOCATION_ALIASES = {
    "austin": "AUS",
    "bangkok": "BKK",
    "boston": "BOS",
    "chicago": "CHI",
    "cluj": "CLJ",
    "cluj napoca": "CLJ",
    "copenhaga": "CPH",
    "copenhagen": "CPH",
    "lisbon": "LIS",
    "london": "LON",
    "mexico city": "MEX",
    "new york": "NYC",
    "paris": "PAR",
    "seoul": "SEL",
    "sydney": "SYD",
    "tokyo": "TYO",
}


def mock_destination_researcher(query: DestinationResearchQuery) -> DestinationResearch:
    focus = focus_items(query.mood)
    memory_tip = query.memory[0].detail if query.memory else "No saved traveler preference yet."

    return DestinationResearch(
        destination=query.destination,
        summary=(
            f"{query.destination} is best approached as a {query.mood.lower()} trip "
            "with flexible neighborhood blocks and room for local discoveries."
        ),
        highlights=[
            f"{query.destination} {focus[0]}",
            f"{query.destination} {focus[1]}",
            f"{query.destination} {focus[2]}",
        ],
        cautions=research_cautions(query),
        local_tips=[
            "Keep one open block each full day for weather or local recommendations.",
            f"Traveler context: {memory_tip}",
        ],
    )


def rule_based_itinerary_planner(planning_input: ItineraryPlanningInput) -> list[TripOption]:
    focus = focus_items(planning_input.mood)
    route = f"{planning_input.origin} -> {planning_input.destination}"

    return [
        TripOption(
            name=fare.name,
            route=route,
            fare=fare.fare,
            score=fare.score,
            meta=fare.meta,
            days=trip_days(fare.name, focus, planning_input),
        )
        for fare in planning_input.fares
    ]


class OpenAIPlannerError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAIPlannerConfig:
    api_key: str
    model: str = "gpt-5.5"
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 30
    reasoning_effort: str = "low"


@dataclass(frozen=True)
class OpenAIItineraryPlanner:
    config: OpenAIPlannerConfig

    @classmethod
    def from_environment(cls) -> Optional["OpenAIItineraryPlanner"]:
        config = openai_config_from_environment()
        if config is None:
            return None

        return cls(config=config)

    def plan(self, planning_input: ItineraryPlanningInput) -> list[TripOption]:
        response = post_openai_response(self.config, self.request_body(planning_input))
        content = extract_output_text(response)
        payload = parse_model_payload(content)
        trips = [TripOption(**trip) for trip in payload["trips"]]

        if not trips:
            raise OpenAIPlannerError("The OpenAI planner returned no trip options.")

        return trips

    def request_body(self, planning_input: ItineraryPlanningInput) -> dict[str, Any]:
        return structured_response_body(
            config=self.config,
            system=(
                "You are a travel planning agent. Produce practical, mobile-friendly "
                "trip options that respect fare data, destination research, constraints, "
                "and saved memory. Return only data that matches the response schema."
            ),
            user_payload=model_prompt_payload(planning_input),
            schema_name="travel_itinerary_options",
            schema=itinerary_response_schema(),
        )


@dataclass(frozen=True)
class OpenAIDestinationResearcher:
    config: OpenAIPlannerConfig

    @classmethod
    def from_environment(cls) -> Optional["OpenAIDestinationResearcher"]:
        config = openai_config_from_environment()
        if config is None:
            return None

        return cls(config=config)

    def research(self, query: DestinationResearchQuery) -> DestinationResearch:
        response = post_openai_response(self.config, self.request_body(query))
        payload = parse_json_object(extract_output_text(response))
        return DestinationResearch(**payload)

    def request_body(self, query: DestinationResearchQuery) -> dict[str, Any]:
        return structured_response_body(
            config=self.config,
            system=(
                "You are a destination research agent. Produce concise planning context "
                "for the requested destination. Do not claim live opening hours, prices, "
                "or availability unless supplied. Use constraints and saved preferences."
            ),
            user_payload=destination_research_prompt_payload(query),
            schema_name="destination_research",
            schema=destination_research_schema(),
        )


@dataclass(frozen=True)
class OpenAIItineraryReviser:
    config: OpenAIPlannerConfig

    @classmethod
    def from_environment(cls) -> Optional["OpenAIItineraryReviser"]:
        config = openai_config_from_environment()
        if config is None:
            return None

        return cls(config=config)

    def revise(self, revision_input: ItineraryRevisionInput) -> TripOption:
        response = post_openai_response(self.config, self.request_body(revision_input))
        payload = parse_json_object(extract_output_text(response))
        revised = TripOption(**payload)
        return TripOption(
            name=revision_input.original_trip.name,
            route=revision_input.original_trip.route,
            fare=revision_input.original_trip.fare,
            score=revised.score,
            meta=add_meta_flag(revised.meta, "critic-reviewed"),
            days=revised.days,
        )

    def request_body(self, revision_input: ItineraryRevisionInput) -> dict[str, Any]:
        return structured_response_body(
            config=self.config,
            system=(
                "You are an itinerary revision agent. Modify the rejected itinerary "
                "so it resolves the critic issues while preserving the fare, route, "
                "and mobile-friendly response schema. Return only schema-matching data."
            ),
            user_payload=revision_prompt_payload(revision_input),
            schema_name="travel_itinerary_revision",
            schema=trip_option_schema(),
        )


def openai_config_from_environment() -> Optional[OpenAIPlannerConfig]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    return OpenAIPlannerConfig(
        api_key=api_key,
        model=os.environ.get("OPENAI_MODEL", "gpt-5.5").strip() or "gpt-5.5",
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
        or "https://api.openai.com/v1",
        timeout_seconds=float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "30")),
        reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", "low").strip() or "low",
    )


def post_openai_response(
    config: OpenAIPlannerConfig,
    request_body: dict[str, Any],
) -> dict[str, Any]:
    request = urllib.request.Request(
        url=f"{config.base_url.rstrip('/')}/responses",
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise OpenAIPlannerError(
            f"OpenAI request failed with status {error.code}: {error_body}"
        ) from error
    except urllib.error.URLError as error:
        raise OpenAIPlannerError(f"OpenAI request failed: {error.reason}") from error


def structured_response_body(
    config: OpenAIPlannerConfig,
    system: str,
    user_payload: dict[str, Any],
    schema_name: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": config.model,
        "input": [
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": json.dumps(user_payload, indent=2),
            },
        ],
        "store": False,
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": schema,
                "strict": True,
            },
            "verbosity": "low",
        },
    }

    if supports_reasoning(config.model):
        body["reasoning"] = {"effort": config.reasoning_effort}

    return body


def model_backed_destination_researcher(query: DestinationResearchQuery) -> DestinationResearch:
    researcher = OpenAIDestinationResearcher.from_environment()
    if researcher is None:
        return mock_destination_researcher(query)

    return researcher.research(query)


def model_backed_itinerary_planner(planning_input: ItineraryPlanningInput) -> list[TripOption]:
    planner = OpenAIItineraryPlanner.from_environment()
    if planner is None:
        return rule_based_itinerary_planner(planning_input)

    return planner.plan(planning_input)


def model_backed_itinerary_reviser(revision_input: ItineraryRevisionInput) -> TripOption:
    reviser = OpenAIItineraryReviser.from_environment()
    if reviser is None:
        return rule_based_itinerary_reviser(revision_input)

    return reviser.revise(revision_input)


def destination_research_prompt_payload(query: DestinationResearchQuery) -> dict[str, Any]:
    return {
        "trip": {
            "origin": query.origin,
            "destination": query.destination,
            "departDate": query.depart_date.isoformat(),
            "returnDate": query.return_date.isoformat(),
            "durationDays": trip_duration_from_dates(query.depart_date, query.return_date),
            "budget": query.budget,
            "mood": query.mood,
            "constraints": query.constraints,
        },
        "memory": [
            {
                "title": note.title,
                "detail": note.detail,
            }
            for note in query.memory
        ],
        "successCriteria": [
            "Return concise research context for itinerary planning.",
            "Prefer experience types over unverifiable live details.",
            "Include practical cautions for the traveler constraints and budget.",
            "Keep the result compact enough to pass into later itinerary prompts.",
        ],
    }


def model_prompt_payload(planning_input: ItineraryPlanningInput) -> dict[str, Any]:
    return {
        "trip": {
            "origin": planning_input.origin,
            "destination": planning_input.destination,
            "departDate": planning_input.depart_date.isoformat(),
            "returnDate": planning_input.return_date.isoformat(),
            "durationDays": planning_input.duration,
            "budget": planning_input.budget,
            "mood": planning_input.mood,
            "constraints": planning_input.constraints,
        },
        "memory": [
            {
                "title": note.title,
                "detail": note.detail,
            }
            for note in planning_input.memory
        ],
        "fares": [
            {
                "name": fare.name,
                "fare": fare.fare,
                "score": fare.score,
                "meta": fare.meta,
            }
            for fare in planning_input.fares
        ],
        "destinationResearch": destination_research_payload(planning_input.destination_research),
        "successCriteria": [
            "Return one itinerary per fare option.",
            "Keep each option concise enough for a mobile card.",
            "Use day labels such as D1, D2, and D3.",
            "Preserve each fare option's name, fare, score, and meta values.",
            "Use destinationResearch highlights and cautions when choosing day details.",
        ],
    }


def revision_prompt_payload(revision_input: ItineraryRevisionInput) -> dict[str, Any]:
    request = revision_input.request
    return {
        "tripRequest": {
            "origin": request.origin,
            "destination": request.destination,
            "departDate": request.departDate.isoformat(),
            "returnDate": request.returnDate.isoformat(),
            "durationDays": trip_duration(request),
            "budget": request.budget,
            "mood": request.mood,
            "constraints": request.constraints,
        },
        "memory": [
            {
                "title": note.title,
                "detail": note.detail,
            }
            for note in request.memory
        ],
        "destinationResearch": destination_research_payload(revision_input.destination_research),
        "originalTrip": trip_option_payload(revision_input.original_trip),
        "critique": {
            "score": revision_input.critic_score,
            "issues": revision_input.issues,
            "recommendations": revision_input.recommendations,
        },
        "successCriteria": [
            "Return exactly one revised option as a trip object.",
            "Preserve originalTrip.name, originalTrip.route, and originalTrip.fare.",
            "Resolve each critic issue in the itinerary text, not by appending a note.",
            "Keep each day concise enough for a mobile trip card.",
            "Respect destinationResearch cautions while revising day details.",
            "Add critic-reviewed to meta once the revision is complete.",
        ],
    }


def destination_research_payload(
    destination_research: Optional[DestinationResearch],
) -> dict[str, Any]:
    if destination_research is None:
        return {
            "destination": "",
            "summary": "",
            "highlights": [],
            "cautions": [],
            "local_tips": [],
        }

    return {
        "destination": destination_research.destination,
        "summary": destination_research.summary,
        "highlights": destination_research.highlights,
        "cautions": destination_research.cautions,
        "local_tips": destination_research.local_tips,
    }


def trip_option_payload(trip: TripOption) -> dict[str, Any]:
    return {
        "name": trip.name,
        "route": trip.route,
        "fare": trip.fare,
        "score": trip.score,
        "meta": trip.meta,
        "days": [
            {
                "label": day.label,
                "title": day.title,
                "detail": day.detail,
            }
            for day in trip.days
        ],
    }


def trip_day_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "label": {"type": "string"},
            "title": {"type": "string"},
            "detail": {"type": "string"},
        },
        "required": ["label", "title", "detail"],
    }


def trip_option_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "route": {"type": "string"},
            "fare": {"type": "number"},
            "score": {"type": "integer"},
            "meta": {"type": "string"},
            "days": {
                "type": "array",
                "items": trip_day_schema(),
            },
        },
        "required": ["name", "route", "fare", "score", "meta", "days"],
    }


def itinerary_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "trips": {
                "type": "array",
                "items": trip_option_schema(),
            }
        },
        "required": ["trips"],
    }


def destination_research_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "destination": {"type": "string"},
            "summary": {"type": "string"},
            "highlights": {
                "type": "array",
                "items": {"type": "string"},
            },
            "cautions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "local_tips": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["destination", "summary", "highlights", "cautions", "local_tips"],
    }


def extract_output_text(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text

    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return content["text"]

    raise OpenAIPlannerError("OpenAI planner response did not include output text.")


def parse_model_payload(content: str) -> dict[str, Any]:
    payload = parse_json_object(content)
    if not isinstance(payload.get("trips"), list):
        raise OpenAIPlannerError("OpenAI planner response did not match the expected contract.")

    return payload


def parse_json_object(content: str) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise OpenAIPlannerError("OpenAI response was not valid JSON.") from error

    if not isinstance(payload, dict):
        raise OpenAIPlannerError("OpenAI response did not match the expected object contract.")

    return payload


def supports_reasoning(model: str) -> bool:
    normalized_model = model.lower()
    return normalized_model.startswith("gpt-5") or normalized_model.startswith("o")


default_tool_router = TravelPlanningToolRouter(
    flight_provider=configured_flight_provider,
    itinerary_planner=model_backed_itinerary_planner,
    location_resolver=cached_location_resolver,
    destination_researcher=model_backed_destination_researcher,
    itinerary_reviser=model_backed_itinerary_reviser,
)


def search_flights(request: TripPlanRequest) -> list[FareOption]:
    return default_tool_router.search_flights(request)


def research_destination(request: TripPlanRequest) -> DestinationResearch:
    return default_tool_router.research_destination(request)


def build_itinerary(
    request: TripPlanRequest,
    fares: list[FareOption],
    destination_research: Optional[DestinationResearch] = None,
) -> list[TripOption]:
    return default_tool_router.build_itinerary(request, fares, destination_research)


def revise_itinerary(
    request: TripPlanRequest,
    trip: TripOption,
    critic_score: int,
    issues: list[str],
    recommendations: list[str],
    destination_research: Optional[DestinationResearch] = None,
) -> TripOption:
    return default_tool_router.revise_itinerary(
        request=request,
        trip=trip,
        critic_score=critic_score,
        issues=issues,
        recommendations=recommendations,
        destination_research=destination_research,
    )


def trip_duration(request: TripPlanRequest) -> int:
    return trip_duration_from_dates(request.departDate, request.returnDate)


def trip_duration_from_dates(depart_date: datetime, return_date: datetime) -> int:
    duration = (return_date - depart_date).days
    return min(max(duration, 3), 10)


def rule_based_itinerary_reviser(revision_input: ItineraryRevisionInput) -> TripOption:
    trip = revision_input.original_trip
    days = [
        revise_day(day, revision_input)
        for day in trip.days
    ]

    if not days:
        days = [
            TripDay(
                label="D1",
                title="Practical reset",
                detail="Add one concrete plan with a flexible buffer and traveler constraints honored.",
            )
        ]

    return TripOption(
        name=trip.name,
        route=trip.route,
        fare=trip.fare,
        score=max(revision_input.critic_score, min(trip.score, 90)),
        meta=critic_reviewed_meta(trip.meta),
        days=days,
    )


def revise_day(day: TripDay, revision_input: ItineraryRevisionInput) -> TripDay:
    detail = day.detail

    if day_has_issue(day, revision_input.issues) and detail_is_overpacked(detail):
        detail = relaxed_day_detail(detail)

    if should_surface_constraints(day, revision_input):
        detail = f"{detail} Constraints honored: {revision_input.request.constraints}"

    if trip_is_over_budget(revision_input):
        detail = f"{detail} Prioritize free sights and flexible meal choices to protect the budget."

    return TripDay(
        label=day.label,
        title=day.title,
        detail=detail,
    )


def day_has_issue(day: TripDay, issues: list[str]) -> bool:
    return any(issue.startswith(day.label) for issue in issues)


def detail_is_overpacked(detail: str) -> bool:
    separators = detail.count(",") + detail.count(";")
    return separators >= 4


def relaxed_day_detail(detail: str) -> str:
    activities = [part.strip() for part in detail.split(",") if part.strip()]
    if len(activities) < 3:
        return f"{detail} Add a protected break before the next commitment."

    return f"{activities[0]}, {activities[1]}, then a protected break before dinner."


def should_surface_constraints(day: TripDay, revision_input: ItineraryRevisionInput) -> bool:
    constraints = revision_input.request.constraints.strip()
    if not constraints or day.label != "D1":
        return False

    trip_text = json.dumps(trip_option_payload(revision_input.original_trip)).lower()
    return constraints.lower() not in trip_text


def trip_is_over_budget(revision_input: ItineraryRevisionInput) -> bool:
    return any("budget" in issue.lower() for issue in revision_input.issues)


def critic_reviewed_meta(meta: str) -> str:
    return add_meta_flag(meta, "critic-reviewed")


def add_meta_flag(meta: str, flag: str) -> str:
    if flag in meta:
        return meta

    return f"{meta} | {flag}"


def research_cautions(query: DestinationResearchQuery) -> list[str]:
    cautions = [
        "Avoid stacking too many cross-town activities into one day.",
    ]

    if query.constraints:
        cautions.append(f"Traveler constraint: {query.constraints}")

    if query.budget < 900:
        cautions.append("Prefer free sights, public transit, and flexible meal choices.")

    return cautions


def focus_items(mood: str) -> list[str]:
    normalized_mood = mood.lower()
    if normalized_mood == "food":
        return ["market crawl", "chef counter", "dessert stop"]
    if normalized_mood == "recharge":
        return ["spa morning", "garden walk", "slow cafe"]
    return ["tile museum", "old town walk", "riverfront concert"]


def trip_days(
    plan_name: str,
    focus: list[str],
    planning_input: ItineraryPlanningInput,
) -> list[TripDay]:
    planning_note = traveler_context_note(planning_input)
    research_note = research_context_note(planning_input.destination_research)
    first_highlight = research_highlight(planning_input.destination_research, 0, focus[0])
    second_highlight = research_highlight(planning_input.destination_research, 1, focus[1])
    third_highlight = research_highlight(planning_input.destination_research, 2, focus[2])

    if plan_name == "Lowest Fare":
        return [
            TripDay(label="D1", title="Fly lean", detail="Carry-on timing with a low-risk connection window."),
            TripDay(label="D2", title="Local layer", detail=f"{first_highlight} plus a neighborhood dinner reservation."),
            TripDay(label="D3", title="Flexible finish", detail=join_notes(planning_note, research_note)),
        ]

    if plan_name == "Comfort Pick":
        return [
            TripDay(label="D1", title="Direct arrival", detail="Midday landing, easy transfer, no late-night commitments."),
            TripDay(label="D2", title="Prime slot", detail=f"{second_highlight} anchored by the highest-fit booking window."),
            TripDay(label="D3", title="Buffer day", detail=join_notes(f"{third_highlight} plus {planning_note}", research_note)),
        ]

    return [
        TripDay(label="D1", title="Arrive light", detail=f"{first_highlight} after check-in, early dinner near the hotel."),
        TripDay(label="D2", title="Deep day", detail=f"{second_highlight} with a protected two-hour open block."),
        TripDay(label="D3", title="Easy close", detail=join_notes(
            f"{third_highlight} before a late afternoon return. {planning_note}",
            research_note,
        )),
    ]


def traveler_context_note(planning_input: ItineraryPlanningInput) -> str:
    if planning_input.constraints:
        return f"Constraints folded in: {planning_input.constraints}"

    if planning_input.memory:
        return f"Saved preference considered: {planning_input.memory[0].detail}"

    return "Open morning held for weather or saved recommendations."


def join_notes(*notes: str) -> str:
    return " ".join(note.strip() for note in notes if note.strip())


def research_context_note(destination_research: Optional[DestinationResearch]) -> str:
    if destination_research is None or not destination_research.local_tips:
        return ""

    return f"Research tip: {destination_research.local_tips[0]}"


def research_highlight(
    destination_research: Optional[DestinationResearch],
    index: int,
    fallback: str,
) -> str:
    if destination_research is None or index >= len(destination_research.highlights):
        return fallback

    return destination_research.highlights[index]
