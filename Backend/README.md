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

`POST /trip-plans` matches the contract documented in the root `README.md`.

## Agent Runtime

The backend is the agent runtime for the iOS client. FastAPI receives `POST /trip-plans`, then `TripCoordinatorAgent` orchestrates the existing flight tool, `ItineraryAgent`, and `ItineraryCriticAgent`. SwiftUI remains the presentation layer and talks to this backend through the existing API contract.

Current split:

- Flight search: tool through `TravelPlanningToolRouter`.
- Itinerary planning and revision: `ItineraryAgent`, backed by the existing rule-based or OpenAI planner/reviser.
- Quality control: `ItineraryCriticAgent`, with deterministic guardrails and a single revise pass when a trip is rejected.
- Coordination and memory: `TripCoordinatorAgent`.

The feedback loop is now: generate itinerary, evaluate it, revise rejected options, then update memory for the iOS client response.

## Model-backed Planning

Set `OPENAI_API_KEY` to enable the model-backed itinerary planner and reviser. Without an API key, the backend keeps using local rule-based planning and revision.

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

## Next Integration Points

- Replace `search_flights()` in `app/tools.py` with a real flight provider.
- Add a destination research agent before itinerary generation.
- Move long-running work into a job or workflow if provider calls become slow.
