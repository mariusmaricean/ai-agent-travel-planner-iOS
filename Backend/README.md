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
- `POST /trip-plans/runs`
- `GET /trip-plans/runs/{runId}`
- `GET /trip-plans/runs/{runId}/events`

`POST /trip-plans` matches the contract documented in the root `README.md`.

Use `POST /trip-plans/runs` when the client wants live progress. The response contains a `runId`, current `status`, emitted `events`, optional final `result`, and optional `error`. Poll `GET /trip-plans/runs/{runId}/events` until `status` is `completed` or `failed`.

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
- Destination research: `DestinationResearchAgent`, using a model-backed research tool when `OPENAI_API_KEY` is configured and a deterministic fallback otherwise.
- Itinerary planning: `ItineraryAgent`, backed by the existing rule-based or OpenAI planner.
- Quality control: `ItineraryCriticAgent`, kept deterministic for fast guardrail checks.
- Revision: a rejected itinerary is sent back through a dedicated reviser that makes concrete day-plan changes; with OpenAI enabled this is a structured model call, otherwise a deterministic fallback is used.
- Coordination and memory: `TripCoordinatorAgent`.
- Progress events: `TripPlanRunStore` captures coordinator events for iOS polling.

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
```

The provider accepts three-letter IATA city or airport codes directly. It resolves city names through Amadeus Airport & City Search when Amadeus credentials are configured, with a small local alias table for common demo names such as New York, Lisbon, Copenhagen, and Cluj-Napoca.

## Next Integration Points

- Cache resolved locations so repeated searches avoid extra provider calls.
- Move long-running work into a job or workflow if provider calls become slow.
