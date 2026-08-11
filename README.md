# Travel Planner for iOS

This is a SwiftUI-native travel planner that treats the iOS app as the agent client and the Python backend as the agent runtime.

## Files

- `TravelPlanner.xcodeproj`: Xcode project with a single SwiftUI iOS app target.
- `TravelPlannerApp.swift`: SwiftUI app shell with trip brief, agent run timeline, saved trips, and local memory.
- `Assets.xcassets/TravelPlannerHero.imageset`: generated travel visual used by the iOS hero.
- `Backend/`: FastAPI agent runtime for the live `POST /trip-plans` endpoint.
- `AGENTS.md`: repository rules and Swift/SwiftUI guidance for AI coding assistants.

## AGENTS.md

This repository uses `AGENTS.md` as the single guidance file for AI coding assistants. Credit for the base guidance goes to [SwiftAgents](https://github.com/twostraws/SwiftAgents) by Paul Hudson, an AGENTS.md file for Swift and SwiftUI projects. Read it before making changes so code edits follow the project context, Swift conventions, and verification expectations.

## Architecture

The app is split into a lightweight iOS client and a backend agent runtime. Keep core agents on the backend so model calls, external APIs, tool execution, retries, prompt logic, and memory updates stay easier to test, secure, and change without shipping a new app build.

### iOS client

- UI
- Trip form
- User interactions
- Display agent progress
- Display itinerary
- Local caching
- Notifications


### Backend runtime

- Coordinator Agent
- Research Agent
- Itinerary Agent
- Critic Agent
- Memory / traveler profile
- OpenAI calls
- Places / Maps / Flights / Weather tools
- Retry / revision loops

### Request lifecycle

```text
SwiftUI
   ↓
AgentViewModel
   ↓
API Client
   ↓
FastAPI
   ↓
TripCoordinatorAgent
   ├── ResearchAgent
   ├── ItineraryAgent
   ├── CriticAgent
   └── Tools
```

## Run

Open `TravelPlanner.xcodeproj` in Xcode, select the `TravelPlanner` scheme, and run it on an iPhone simulator or device.

To run the backend locally:

```bash
cd Backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Agent Integration Points
- Set `TRAVEL_PLANNER_API_BASE_URL` to use the live backend instead of the local mock planner.
- Route `searchFlights(origin, destination, dates, budget)` to a flight provider function.
- Route `buildItinerary(fares, constraints, memory)` to your planning/model function.
- Route rejected plans through the backend itinerary reviser so the critic feedback changes the itinerary content.
- Return updated `memory` from the backend, or omit it to keep the local memory update.
- Add a destination research agent before itinerary generation.

The local Swift planner remains useful as a preview/fallback experience. Production intelligence and orchestration should stay behind the backend API.

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
