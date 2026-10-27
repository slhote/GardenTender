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
uv run alembic upgrade head              # create/upgrade the schema
uv run uvicorn app.main:app --reload --host 0.0.0.0
uv run pytest                            # tests (no network or API key needed)
```
You can test the api is up and running by navigating to `http://localhost:8000/docs` in any browser connected to the same network.  
Tests use a throwaway SQLite file, so they need no Docker, Postgres or API key. The schema is managed by Alembic: change `app/models.py`, then `uv run alembic revision --autogenerate -m "..."` and review the generated file. Docker runs `alembic upgrade head` before starting the API. `tests/test_migrations.py` fails if migrations and models drift.

If your local database predates Alembic, wipe it once: `docker compose down -v`.

## Public links in local dev (invites, QR codes)

Invite emails and QR codes link to `PUBLIC_BASE_URL` (`/i/<token>`, `/q/<token>`). Android App Links only open in the app when that origin is public **https** and serves `/.well-known/assetlinks.json`, so locally the API is exposed through an [ngrok](https://ngrok.com) static domain, the same way it will run behind a real domain later:

1. Create a free ngrok account, install the agent, and claim your free static domain (e.g. `yourname.ngrok-free.app`).
2. Run the tunnel to the API:
   ```bash
   ngrok http --url=yourname.ngrok-free.app 8000
   ```
3. In `.env`, set `PUBLIC_BASE_URL=https://yourname.ngrok-free.app`, plus `ANDROID_PACKAGE` and `ANDROID_CERT_SHA256` (the debug keystore's SHA-256 from `./gradlew signingReport`, as a JSON list).
4. Point the app's `api.baseUrl` and App Links host at the same domain in `local.properties`.

Moving to a real domain later (e.g. Cloudflare Tunnel) only changes `PUBLIC_BASE_URL` and the app's host. Emails are written to the API log (`EMAIL_BACKEND=console`) until a provider is chosen.
