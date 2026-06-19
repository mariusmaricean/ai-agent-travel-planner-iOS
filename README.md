# Travel Planner for iOS

This is a SwiftUI-native version of the mobile-first autonomous travel agent prototype.

## Files

- `TravelPlanner.xcodeproj`: Xcode project with a single SwiftUI iOS app target.
- `TravelPlannerApp.swift`: complete SwiftUI app shell with trip brief, agent run timeline, saved trips, and UserDefaults-backed memory.
- `Assets.xcassets/TravelPlannerHero.imageset`: generated travel visual used by the iOS hero.

## Run

Open `TravelPlanner.xcodeproj` in Xcode, select the `TravelPlanner` scheme, and run it on an iPhone simulator or device.

## Agent Integration Points
- Set `TRAVEL_PLANNER_API_BASE_URL` to use the live backend instead of the local mock planner.
- Implement `POST /trip-plans` on your backend.
- Route `searchFlights(origin, destination, dates, budget)` to a flight provider function.
- Route `buildItinerary(fares, constraints, memory)` to your planning/model function.
- Return updated `memory` from the backend, or omit it to keep the local memory update.

The included implementation intentionally simulates tool calls on-device so the UI can run before any API keys, auth, or backend wiring exists.

### `POST /trip-plans`

Request:

```json
{
  "origin": "New York",
  "destination": "Lisbon",
  "departDate": "2026-07-11T09:00:00.000Z",
  "returnDate": "2026-07-16T09:00:00.000Z",
  "budget": 1400,
  "constraints": "Window seat, no red-eye flights.",
  "rememberPreferences": true,
  "mood": "Culture",
  "memory": [
    { "title": "Travel preference", "detail": "Culture trips under $1,400." }
  ]
}
```

Response:

```json
{
  "trips": [
    {
      "name": "Balanced Sprint",
      "route": "New York -> Lisbon",
      "fare": 1470,
      "score": 94,
      "meta": "5 days | morning outbound | 1 checked bag",
      "days": [
        { "label": "D1", "title": "Arrive light", "detail": "Old town walk after check-in." }
      ]
    }
  ],
  "memory": [
    { "title": "Last best option", "detail": "Balanced Sprint to Lisbon at $1,470." }
  ]
}
```
