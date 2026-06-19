from datetime import datetime, timezone

from app.planner import create_trip_plan
from app.schemas import TripPlanRequest


def test_create_trip_plan_returns_contract_shape() -> None:
    request = TripPlanRequest(
        origin="New York",
        destination="Lisbon",
        departDate=datetime(2026, 7, 11, 9, tzinfo=timezone.utc),
        returnDate=datetime(2026, 7, 16, 9, tzinfo=timezone.utc),
        budget=1400,
        constraints="Window seat, no red-eye flights.",
        rememberPreferences=True,
        mood="Culture",
        memory=[],
    )

    response = create_trip_plan(request)

    assert len(response.trips) == 3
    assert response.trips[0].route == "New York -> Lisbon"
    assert response.trips[0].days[0].label == "D1"
    assert response.memory is not None
    assert response.memory[-1].title == "Last best option"
