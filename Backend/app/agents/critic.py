from dataclasses import dataclass, field

from app.schemas import TripOption, TripPlanRequest


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

        if not trip.days:
            issues.append("Trip does not include any itinerary days.")
            recommendations.append("Add at least one concrete day plan.")

        if request.constraints and ignores_constraints(request, trip):
            issues.append("Trip does not visibly address traveler constraints.")
            recommendations.append("Make the saved constraints explicit in the itinerary notes.")

        for day in trip.days:
            if detail_looks_overpacked(day.detail):
                issues.append(f"{day.label} may be too packed for a mobile travel plan.")
                recommendations.append("Add a protected break or reduce the number of activities.")

        score = max(50, trip.score - (len(issues) * 12))
        return Critique(
            approved=not issues,
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
