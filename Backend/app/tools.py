import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from dotenv import load_dotenv

from app.schemas import MemoryNote, TripDay, TripOption, TripPlanRequest

load_dotenv()


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


@dataclass(frozen=True)
class ItineraryRevisionInput:
    request: TripPlanRequest
    original_trip: TripOption
    critic_score: int
    issues: list[str]
    recommendations: list[str]


FlightProviderFunction = Callable[[FlightSearchQuery], list[FareOption]]
ItineraryPlannerFunction = Callable[[ItineraryPlanningInput], list[TripOption]]
ItineraryReviserFunction = Callable[[ItineraryRevisionInput], TripOption]


@dataclass(frozen=True)
class TravelPlanningToolRouter:
    flight_provider: FlightProviderFunction
    itinerary_planner: ItineraryPlannerFunction
    itinerary_reviser: Optional[ItineraryReviserFunction] = None

    def search_flights(self, request: TripPlanRequest) -> list[FareOption]:
        query = FlightSearchQuery(
            origin=request.origin,
            destination=request.destination,
            depart_date=request.departDate,
            return_date=request.returnDate,
            budget=request.budget,
        )
        return self.flight_provider(query)

    def build_itinerary(
        self,
        request: TripPlanRequest,
        fares: list[FareOption],
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
        )
        return self.itinerary_planner(planning_input)

    def revise_itinerary(
        self,
        request: TripPlanRequest,
        trip: TripOption,
        critic_score: int,
        issues: list[str],
        recommendations: list[str],
    ) -> TripOption:
        revision_input = ItineraryRevisionInput(
            request=request,
            original_trip=trip,
            critic_score=critic_score,
            issues=issues,
            recommendations=recommendations,
        )
        reviser = self.itinerary_reviser or model_backed_itinerary_reviser
        return reviser(revision_input)


def mock_flight_provider(query: FlightSearchQuery) -> list[FareOption]:
    base_fare = max(320, round(query.budget * 0.42))
    duration = trip_duration_from_dates(query.depart_date, query.return_date)

    return [
        FareOption(
            name="Balanced Sprint",
            fare=base_fare + 70,
            score=94,
            meta=f"{duration} days | morning outbound | 1 checked bag",
        ),
        FareOption(
            name="Lowest Fare",
            fare=base_fare - 45,
            score=88,
            meta=f"{duration} days | one connection | budget winner",
        ),
        FareOption(
            name="Comfort Pick",
            fare=base_fare + 180,
            score=91,
            meta=f"{duration} days | direct flight | aisle-friendly timing",
        ),
    ]


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
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            return None

        return cls(
            config=OpenAIPlannerConfig(
                api_key=api_key,
                model=os.environ.get("OPENAI_MODEL", "gpt-5.5").strip() or "gpt-5.5",
                base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
                or "https://api.openai.com/v1",
                timeout_seconds=float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "30")),
                reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", "low").strip() or "low",
            )
        )

    def plan(self, planning_input: ItineraryPlanningInput) -> list[TripOption]:
        response = self.create_response(planning_input)
        content = extract_output_text(response)
        payload = parse_model_payload(content)
        trips = [TripOption(**trip) for trip in payload["trips"]]

        if not trips:
            raise OpenAIPlannerError("The OpenAI planner returned no trip options.")

        return trips

    def revise(self, revision_input: ItineraryRevisionInput) -> TripOption:
        response = self.create_revision_response(revision_input)
        content = extract_output_text(response)
        payload = parse_model_payload(content)
        trips = [TripOption(**trip) for trip in payload["trips"]]

        if not trips:
            raise OpenAIPlannerError("The OpenAI planner returned no revised trip option.")

        return trips[0]

    def create_response(self, planning_input: ItineraryPlanningInput) -> dict[str, Any]:
        return self.send_request(self.request_body(planning_input))

    def create_revision_response(self, revision_input: ItineraryRevisionInput) -> dict[str, Any]:
        return self.send_request(self.revision_request_body(revision_input))

    def send_request(self, request_body: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url=f"{self.config.base_url.rstrip('/')}/responses",
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            raise OpenAIPlannerError(
                f"OpenAI planner request failed with status {error.code}: {error_body}"
            ) from error
        except urllib.error.URLError as error:
            raise OpenAIPlannerError(f"OpenAI planner request failed: {error.reason}") from error

    def request_body(self, planning_input: ItineraryPlanningInput) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.config.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You are a travel planning agent. Produce practical, mobile-friendly "
                        "trip options that respect fare data, constraints, and saved memory. "
                        "Return only data that matches the response schema."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(model_prompt_payload(planning_input), indent=2),
                },
            ],
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "travel_itinerary_options",
                    "schema": itinerary_response_schema(),
                    "strict": True,
                },
                "verbosity": "low",
            },
        }

        if supports_reasoning(self.config.model):
            body["reasoning"] = {"effort": self.config.reasoning_effort}

        return body

    def revision_request_body(self, revision_input: ItineraryRevisionInput) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.config.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You are an itinerary revision agent. Modify the rejected itinerary "
                        "so it resolves the critic issues while preserving the fare, route, "
                        "and mobile-friendly response schema. Return only schema-matching data."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(revision_prompt_payload(revision_input), indent=2),
                },
            ],
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "travel_itinerary_revision",
                    "schema": itinerary_response_schema(),
                    "strict": True,
                },
                "verbosity": "low",
            },
        }

        if supports_reasoning(self.config.model):
            body["reasoning"] = {"effort": self.config.reasoning_effort}

        return body


def model_backed_itinerary_planner(planning_input: ItineraryPlanningInput) -> list[TripOption]:
    planner = OpenAIItineraryPlanner.from_environment()
    if planner is None:
        return rule_based_itinerary_planner(planning_input)

    return planner.plan(planning_input)


def model_backed_itinerary_reviser(revision_input: ItineraryRevisionInput) -> TripOption:
    planner = OpenAIItineraryPlanner.from_environment()
    if planner is None:
        return rule_based_itinerary_reviser(revision_input)

    return planner.revise(revision_input)


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
        "successCriteria": [
            "Return one itinerary per fare option.",
            "Keep each option concise enough for a mobile card.",
            "Use day labels such as D1, D2, and D3.",
            "Preserve each fare option's name, fare, score, and meta values.",
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
        "originalTrip": trip_option_payload(revision_input.original_trip),
        "critique": {
            "score": revision_input.critic_score,
            "issues": revision_input.issues,
            "recommendations": revision_input.recommendations,
        },
        "successCriteria": [
            "Return exactly one revised option in the trips array.",
            "Preserve originalTrip.name, originalTrip.route, and originalTrip.fare.",
            "Resolve each critic issue in the itinerary text, not by appending a note.",
            "Keep each day concise enough for a mobile trip card.",
            "Add critic-reviewed to meta once the revision is complete.",
        ],
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


def itinerary_response_schema() -> dict[str, Any]:
    trip_day_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "label": {"type": "string"},
            "title": {"type": "string"},
            "detail": {"type": "string"},
        },
        "required": ["label", "title", "detail"],
    }

    trip_option_schema = {
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
                "items": trip_day_schema,
            },
        },
        "required": ["name", "route", "fare", "score", "meta", "days"],
    }

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "trips": {
                "type": "array",
                "items": trip_option_schema,
            }
        },
        "required": ["trips"],
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
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise OpenAIPlannerError("OpenAI planner response was not valid JSON.") from error

    if not isinstance(payload, dict) or not isinstance(payload.get("trips"), list):
        raise OpenAIPlannerError("OpenAI planner response did not match the expected contract.")

    return payload


def supports_reasoning(model: str) -> bool:
    normalized_model = model.lower()
    return normalized_model.startswith("gpt-5") or normalized_model.startswith("o")


default_tool_router = TravelPlanningToolRouter(
    flight_provider=mock_flight_provider,
    itinerary_planner=model_backed_itinerary_planner,
    itinerary_reviser=model_backed_itinerary_reviser,
)


def search_flights(request: TripPlanRequest) -> list[FareOption]:
    return default_tool_router.search_flights(request)


def build_itinerary(
    request: TripPlanRequest,
    fares: list[FareOption],
) -> list[TripOption]:
    return default_tool_router.build_itinerary(request, fares)


def revise_itinerary(
    request: TripPlanRequest,
    trip: TripOption,
    critic_score: int,
    issues: list[str],
    recommendations: list[str],
) -> TripOption:
    return default_tool_router.revise_itinerary(
        request=request,
        trip=trip,
        critic_score=critic_score,
        issues=issues,
        recommendations=recommendations,
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
    if "critic-reviewed" in meta:
        return meta

    return f"{meta} | critic-reviewed"


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

    if plan_name == "Lowest Fare":
        return [
            TripDay(label="D1", title="Fly lean", detail="Carry-on timing with a low-risk connection window."),
            TripDay(label="D2", title="Local layer", detail=f"{focus[0]} plus a neighborhood dinner reservation."),
            TripDay(label="D3", title="Flexible finish", detail=planning_note),
        ]

    if plan_name == "Comfort Pick":
        return [
            TripDay(label="D1", title="Direct arrival", detail="Midday landing, easy transfer, no late-night commitments."),
            TripDay(label="D2", title="Prime slot", detail=f"{focus[1]} anchored by the highest-fit booking window."),
            TripDay(label="D3", title="Buffer day", detail=f"{focus[2]} plus {planning_note}"),
        ]

    return [
        TripDay(label="D1", title="Arrive light", detail=f"{focus[0]} after check-in, early dinner near the hotel."),
        TripDay(label="D2", title="Deep day", detail=f"{focus[1]} with a protected two-hour open block."),
        TripDay(label="D3", title="Easy close", detail=f"{focus[2]} before a late afternoon return. {planning_note}"),
    ]


def traveler_context_note(planning_input: ItineraryPlanningInput) -> str:
    if planning_input.constraints:
        return f"Constraints folded in: {planning_input.constraints}"

    if planning_input.memory:
        return f"Saved preference considered: {planning_input.memory[0].detail}"

    return "Open morning held for weather or saved recommendations."
