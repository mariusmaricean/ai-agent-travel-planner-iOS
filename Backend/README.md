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

## Next Integration Points

- Replace `search_flights()` in `app/tools.py` with a real flight provider.
- Replace `build_itinerary()` in `app/tools.py` with a model-backed planning call.
- Move long-running work into a job or workflow if provider calls become slow.
