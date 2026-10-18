# GardenTender.Api

FastAPI backend for the app's chat. See [PLAN.md](PLAN.md) for design and Auth0 setup.

```bash
cp .env.example .env                     # fill in Auth0 + Anthropic values
docker compose up --build                # Postgres + API at http://localhost:8000/docs
```

Without Docker for the API:

1. Start Postgres db from Docker compose.
```bash
docker compose up -d db
```
2. Then run the api.
```bash
uv sync                                  # install deps
uv run uvicorn app.main:app --reload --host 0.0.0.0
uv run pytest                            # tests (no network or API key needed)
```
You can test the api is up and running by navigating to `http://localhost:8000/docs` in any browser connected to the same network.  
Tests use a throwaway SQLite file, so they need no Docker, Postgres or API key. Tables are created on startup; add Alembic migrations before changing the schema.
