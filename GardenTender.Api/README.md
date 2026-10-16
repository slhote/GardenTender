# GardenTender.Api

FastAPI backend for the app's chat. See [PLAN.md](PLAN.md) for design and Auth0 setup.

```bash
cp .env.example .env                     # fill in Auth0 + Anthropic values
docker compose up --build                # Postgres + API at http://localhost:8000/docs
```

Without Docker for the API (Postgres still from compose: `docker compose up db`):

```bash
uv sync                                  # install deps
uv run uvicorn app.main:app --reload     # run (http://localhost:8000/docs)
uv run pytest                            # tests (no network or API key needed)
```

Tests use a throwaway SQLite file, so they need no Docker, Postgres or API key. Tables are created on startup; add Alembic migrations before changing the schema.
