# Travel Planner for iOS

This is a SwiftUI-native travel planner that treats the iOS app as the agent client and the Python backend as the agent runtime.

## Files

- `TravelPlanner.xcodeproj`: Xcode project with a single SwiftUI iOS app target.
- `TravelPlannerApp.swift`: SwiftUI app shell with trip brief, agent run timeline, saved trips, and local memory.
- `Assets.xcassets/TravelPlannerHero.imageset`: generated travel visual used by the iOS hero.
- `Backend/`: FastAPI agent runtime for direct trip plans and live agent run progress.
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
   ├── Revision loop
   ├── Final critique
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
- Use `POST /trip-plans/runs` and `GET /trip-plans/runs/{runId}/events` to render live agent progress in the iOS timeline.
- Persisted backend run snapshots let iOS keep polling after slow provider calls or backend store recreation.
- Configure `FLIGHT_PROVIDER=amadeus` plus Amadeus credentials to resolve and cache city names, then use real flight offers; without credentials the backend uses the mock provider.
- Set `DESTINATION_RESEARCH_PROVIDER=open_meteo` to enrich destination research with weather context.
- Watch the backend `travel_planner.providers` logger to inspect location resolution, provider usage, failures, and mock fallbacks.
- Route `researchDestination(destination, mood, constraints, memory)` to Places, Maps, Weather, or events data.
- Route `buildItinerary(fares, constraints, memory)` to your planning/model function.
- Route rejected plans through the backend itinerary reviser so the critic feedback changes the itinerary content.
- Return updated `memory` from the backend, or omit it to keep the local memory update.

The local Swift planner remains useful as a preview/fallback experience. Production intelligence and orchestration should stay behind the backend API.

### Backend API

- `POST /trip-plans`: direct trip plan response.
- `POST /trip-plans/runs`: starts a live agent run and returns a run snapshot.
- `GET /trip-plans/runs/{runId}/events`: polls progress events, completion, and failure state.

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

Direct `POST /trip-plans` response:

```json
{
  "trips": [
    {
      "name": "Balanced Sprint",
      "route": "New York -> Lisbon",
      "fare": 1470,
      "score": 94,
      "meta": "5 days | morning outbound | 1 checked bag | source: mock",
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

Run snapshot response:

```json
{
  "runId": "7caa0c0f-4a21-4d90-9f2c-f9c0c9d53a7d",
  "status": "running",
  "events": [
    {
      "id": 1,
      "step": "research",
      "status": "active",
      "title": "Research destination",
      "detail": "Studying Lisbon for culture goals.",
      "createdAt": "2026-07-11T09:00:00Z"
    }
  ],
  "result": null,
  "error": null
}
```
