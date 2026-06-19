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

## Model-backed Planning

Set `OPENAI_API_KEY` to enable the model-backed itinerary planner. Without an API key, the backend keeps using the local rule-based planner.

Keep API keys on the backend only. Do not add OpenAI keys to the iOS app, Swift files, Xcode build settings, or committed files.

For local development, copy the example file and add your rotated key:

```bash
cp .env.example .env
```

Then edit `.env` locally:

```text
OPENAI_API_KEY=your-rotated-key
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
- Move long-running work into a job or workflow if provider calls become slow.
