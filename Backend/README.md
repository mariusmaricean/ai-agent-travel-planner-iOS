# Travel Planner Backend

FastAPI service for the iOS app's live planning mode.

## Run Locally

```bash
cd Backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

For the iOS simulator, set `TRAVEL_PLANNER_API_BASE_URL` to:

```text
http://127.0.0.1:8000
```

## Endpoints

- `GET /health`
- `POST /trip-plans`
- `GET /trip-plans/history`
- `GET /trip-plans/history/{planId}`
- `GET /memory/latest`
- `POST /trip-plans/runs`
- `GET /trip-plans/runs/{runId}`
- `GET /trip-plans/runs/{runId}/events`

`POST /trip-plans` matches the contract documented in the root `README.md`.

Use `POST /trip-plans/runs` when the client wants live progress. The response contains a `runId`, current `status`, emitted `events`, optional final `result`, and optional `error`. Poll `GET /trip-plans/runs/{runId}/events` until `status` is `completed` or `failed`.

Run snapshots are persisted to disk so polling state survives store recreation and backend restarts. Any run that was still `running` during startup is marked `failed` with an interruption message because the in-process worker that owned it is gone.

Completed trip plans are also persisted to disk. Use `GET /trip-plans/history` to list saved plans, `GET /trip-plans/history/{planId}` to fetch one saved response, and `GET /memory/latest` to hydrate the client with the most recent traveler memory.

## Agent Runtime

The backend is the agent runtime for the iOS client. FastAPI receives `POST /trip-plans`; `TripCoordinatorAgent` then runs a bounded agent workflow while SwiftUI stays focused on presentation.

Current flow:

```text
TripCoordinatorAgent
  -> DestinationResearchAgent
  -> flight search tool
  -> ItineraryAgent
  -> ItineraryCriticAgent
  -> ItineraryAgent.revise() when rejected
  -> final critique + response/memory
```

Responsibilities:

- Flight search: `TravelPlanningToolRouter`, using Amadeus Location Search and Flight Offers when configured and the deterministic mock provider otherwise.
- Destination research: `DestinationResearchAgent`, using optional Open-Meteo weather research, a model-backed research tool when `OPENAI_API_KEY` is configured, and a deterministic fallback otherwise.
- Itinerary planning: `ItineraryAgent`, backed by the existing rule-based or OpenAI planner.
- Quality control: `ItineraryCriticAgent`, kept deterministic for fast guardrail checks.
- Revision: a rejected itinerary is sent back through a dedicated reviser that makes concrete day-plan changes; with OpenAI enabled this is a structured model call, otherwise a deterministic fallback is used.
- Coordination and memory: `TripCoordinatorAgent`.
- Progress events: `TripPlanRunStore` persists coordinator events for iOS polling, while `TripPlanJobRunner` runs planning work outside the request/response lifecycle.
- History and memory persistence: `TripPlanHistoryStore` saves completed direct plans and completed live-run plans for later retrieval.

The coordinator intentionally allows only one revision pass so request latency and model cost remain bounded. The revised result is critiqued once more before it is returned.

## Model-backed Planning

Set `OPENAI_API_KEY` to enable the model-backed itinerary planner. Without an API key, the backend keeps using the local rule-based planner.

Keep API keys on the backend only. Do not add OpenAI keys to the iOS app, Swift files, Xcode build settings, or committed files.

For local development, copy the example file and add your local key:

```bash
cp .env.example .env
```

Then edit `.env` locally:

```text
OPENAI_API_KEY=your-local-key
```

Start the server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Optional environment variables:

- `OPENAI_MODEL`: defaults to `gpt-5.5`.
- `OPENAI_BASE_URL`: defaults to `https://api.openai.com/v1`.
- `OPENAI_TIMEOUT_SECONDS`: defaults to `30`.
- `OPENAI_REASONING_EFFORT`: defaults to `low`.
- `TRIP_PLAN_RUN_STORE_PATH`: defaults to `Backend/.data/trip_plan_runs.json`; relative paths are resolved from the `Backend` directory.
- `TRIP_PLAN_RUN_WORKERS`: defaults to `2`.
- `TRIP_PLAN_HISTORY_STORE_PATH`: defaults to `Backend/.data/trip_plan_history.json`; relative paths are resolved from the `Backend` directory.
- `TRIP_PLAN_HISTORY_LIMIT`: defaults to `100`.

## Destination Research Provider

Set `DESTINATION_RESEARCH_PROVIDER=open_meteo` to add real destination weather context from Open-Meteo before itinerary planning. The provider geocodes the destination, fetches a short daily forecast, and turns that into highlights, cautions, and local tips. If the provider is disabled or fails, the backend falls back to model-backed or deterministic research.

```text
DESTINATION_RESEARCH_PROVIDER=open_meteo
OPEN_METEO_GEOCODING_URL=https://geocoding-api.open-meteo.com/v1/search
OPEN_METEO_FORECAST_URL=https://api.open-meteo.com/v1/forecast
OPEN_METEO_TIMEOUT_SECONDS=12
```

When OpenAI is also enabled, the Open-Meteo result is passed into the destination research prompt as provider context.

## Flight Provider

The backend can call Amadeus Self-Service Flight Offers Search when credentials are configured. Without credentials, or when `FLIGHT_PROVIDER=mock`, it keeps using the local mock fare provider.

```text
FLIGHT_PROVIDER=amadeus
AMADEUS_CLIENT_ID=your-client-id
AMADEUS_CLIENT_SECRET=your-client-secret
AMADEUS_BASE_URL=https://test.api.amadeus.com
AMADEUS_CURRENCY_CODE=USD
AMADEUS_MAX_OFFERS=3
AMADEUS_ADULTS=1
LOCATION_CACHE_MAX_ENTRIES=128
PROVIDER_LOG_LEVEL=INFO
```

The provider accepts three-letter IATA city or airport codes directly. It resolves city names through Amadeus Airport & City Search when Amadeus credentials are configured, with a small local alias table for common demo names such as New York, Lisbon, Copenhagen, and Cluj-Napoca. Successful resolutions are cached in memory per backend process.

Provider decisions are logged through the `travel_planner.providers` logger as `provider_event` records. Current events cover local aliases, IATA input, cache hits/stores, Amadeus location lookups, Amadeus flight offers, provider failures, and mock fallbacks.

## Next Integration Points

- Add places or events providers to destination research.
- Scope saved trip history and memory by authenticated user before production.
- Surface provider telemetry in live run events or a monitoring dashboard.
- Move persisted run execution to an external queue or workflow worker before multi-instance deployment.
