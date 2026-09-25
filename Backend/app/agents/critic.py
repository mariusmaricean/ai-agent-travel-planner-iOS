from dataclasses import dataclass, field

from app.schemas import TripOption, TripPlanRequest

MIN_APPROVED_SCORE = 82


@dataclass(frozen=True)
class Critique:
    approved: bool
    score: int
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


class ItineraryCriticAgent:
    def run(
        self,
        request: TripPlanRequest,
        trip: TripOption,
    ) -> Critique:
        issues: list[str] = []
        recommendations: list[str] = []

        if trip.fare > request.budget:
            issues.append("Trip fare exceeds the requested budget.")
            recommendations.append("Revise paid activities or flag the fare as over budget.")
        elif trip.fare > request.budget * 0.92:
            issues.append("Trip fare leaves too little budget buffer.")
            recommendations.append("Add lower-cost alternates and preserve a flexible budget buffer.")

        if not trip.days:
            issues.append("Trip does not include any itinerary days.")
            recommendations.append("Add at least one concrete day plan.")

        if trip.days and len(trip.days) < expected_day_count(request):
            issues.append("Trip does not cover enough days for the requested dates.")
            recommendations.append("Add missing day coverage or explain which days stay flexible.")

        if request.constraints and ignores_constraints(request, trip):
            issues.append("Trip does not visibly address traveler constraints.")
            recommendations.append("Make the saved constraints explicit in the itinerary notes.")

        for day in trip.days:
            if detail_looks_too_thin(day.detail):
                issues.append(f"{day.label} is too vague for a useful itinerary.")
                recommendations.append("Add one concrete anchor and one flexible backup.")

            if detail_looks_overpacked(day.detail):
                issues.append(f"{day.label} may be too packed for a mobile travel plan.")
                recommendations.append("Add a protected break or reduce the number of activities.")

            if detail_has_travel_time_risk(day.detail):
                issues.append(f"{day.label} may include unrealistic travel time.")
                recommendations.append("Cluster activities by neighborhood or add a transit buffer.")

        if has_repetitive_days(trip):
            issues.append("Trip repeats the same day structure too often.")
            recommendations.append("Vary the daily anchors so the plan feels intentional.")

        score = bounded_score(trip.score - (len(issues) * 10))
        return Critique(
            approved=not issues and score >= MIN_APPROVED_SCORE,
            score=score,
            issues=issues,
            recommendations=recommendations,
        )


def ignores_constraints(request: TripPlanRequest, trip: TripOption) -> bool:
    normalized_constraints = request.constraints.lower()
    if "no red-eye" in normalized_constraints or "no red eye" in normalized_constraints:
        trip_text = trip_text_content(trip).lower()
        mentions_red_eye = "red-eye" in trip_text or "red eye" in trip_text
        acknowledges_constraint = "no red-eye" in trip_text or "no red eye" in trip_text
        return mentions_red_eye and not acknowledges_constraint

    return False


def detail_looks_overpacked(detail: str) -> bool:
    separators = detail.count(",") + detail.count(";")
    return separators >= 4


def detail_looks_too_thin(detail: str) -> bool:
    return len(detail.split()) < 6


def detail_has_travel_time_risk(detail: str) -> bool:
    normalized = detail.lower()
    has_transit_signal = any(
        signal in normalized
        for signal in [
            "across town",
            "cross-town",
            "cross town",
            "airport",
            "opposite side",
            "far side",
        ]
    )
    if not has_transit_signal:
        return False

    return detail.count(",") + detail.count(";") >= 2


def has_repetitive_days(trip: TripOption) -> bool:
    if len(trip.days) < 3:
        return False

    normalized_details = {
        " ".join(day.detail.lower().split())
        for day in trip.days
    }
    normalized_titles = {
        " ".join(day.title.lower().split())
        for day in trip.days
    }
    return len(normalized_details) == 1 or len(normalized_titles) == 1


def expected_day_count(request: TripPlanRequest) -> int:
    duration = (request.returnDate - request.departDate).days
    return min(max(duration, 3), 10)


def bounded_score(score: int) -> int:
    return max(40, min(100, score))


def trip_text_content(trip: TripOption) -> str:
    return " ".join(
        [
            trip.name,
            trip.route,
            trip.meta,
            *[day.title for day in trip.days],
            *[day.detail for day in trip.days],
        ]
    )
