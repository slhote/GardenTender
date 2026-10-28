# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Two projects in one repo: `GardenTender.Android` (Kotlin/Compose app) and `GardenTender.Api` (FastAPI chat backend). `make_qr.py` generates test QR codes (`gardentender://plant/<id>[?action=water]`) into `qr_codes/`.

## Commands

### API (`GardenTender.Api`, Python >=3.12, uses `uv`)

```bash
cp .env.example .env                    # then fill in Auth0 / Anthropic / Postgres values
docker compose up --build               # Postgres + API at http://localhost:8000/docs
docker compose up db                    # Postgres only, when running the API locally
uv sync
uv run alembic upgrade head            # schema (Docker does this on start)
uv run uvicorn app.main:app --reload
uv run pytest                           # needs the Postgres container (`docker compose up -d db`); no network or API key
uv run pytest tests/test_chat.py::test_name   # single test
```

Schema changes go through Alembic (`migrations/`): edit `app/models.py`, then `uv run alembic revision --autogenerate -m "..."`. `tests/test_migrations.py` runs the migrations on an empty Postgres database and checks they match the models and downgrade cleanly.

### Android (`GardenTender.Android`)

```powershell
.\gradlew.bat :app:installDebug         # build + install debug APK
```

`.claude/skills/install-debug` builds and installs to a phone over wireless adb. Config comes from `local.properties`: `auth0.domain`, `auth0.clientId`, `auth0.audience`, `api.baseUrl` (default `http://10.0.2.2:8000` works for the emulator only; use the PC's LAN IP for a real phone).

## Architecture

**Chat flow.** The app's chat sheet (`chat/ChatViewModel`, `ChatApi`) calls the API's `/gardens/{id}/chat` with the Auth0 access token (chat requires garden membership; the global admin override doesn't apply). The API runs a provider-agnostic tool-use loop, `run_chat` in `app/llm/loop.py`; `/chat` depends only on that function. `LlmProvider` (`app/llm/base.py`) has Claude and Ollama implementations selected by `LLM_PROVIDER`.

**Tools** are plain data in `app/tools/registry.py` (Pydantic input model, handler, required `GardenPermission`, `confirm`, `runs_on`). Two kinds:
- `runs_on="server"`: handler runs in the API via `app/services/` (shared with the direct endpoints). `confirm=True` pauses for user approval first.
- `runs_on="device"` (`set_reminder`, `add_calendar_event`): the API returns them as pending calls and the Android `chat/DeviceTools` executes them, then sends results back.

**Stateless resume.** There is no server-side conversation state. When a call needs the client, `run_chat` stops and returns the history plus pending calls; the client resends the history with `decisions` / `device_results`. History can be forged, so every executed call is re-validated and checked against the caller's garden role server-side. The model never supplies the user or garden; handlers receive a `ToolContext` (garden id, actor, role) built from the token and membership, and all data access is scoped by the garden. Chat history on the phone is in-memory only by design.

**Auth.** Auth0 RS256 JWTs verified in `app/auth.py`. The only Auth0 permission the API uses is `system:admin` (global admin, from the RBAC `permissions` claim); everything else is a per-garden role. The model only sees tools the caller's garden role allows. The app must request the API audience at login or Auth0 issues an opaque token the API can't verify.

**Gardens and roles.** Per-garden roles (`admin`, `contributor`) live in `garden_members`, not Auth0; `app/roles.py` maps each role to permissions (admin ⊇ contributor). Garden routes depend on `require_garden(permission)`, which resolves membership or the global admin override (Auth0 permission `system:admin`); non-members get 404. Every garden action writes a `garden_events` row in the same transaction, and `app/audit.py` middleware logs every `system:admin` request to `admin_audit_log`. Things a role can't do directly (a contributor adding a plant) go through `garden_requests` (`app/services/requests.py`): each request type is a `RequestKind` (validate + apply on approval), and requesters whose role already allows it are auto-approved. Invites (`app/services/invites.py`) are single-use hashed tokens with an expiry; emails go through the `EmailSender` interface and are queued on a per-request `Notifier` that is flushed only after commit. Printable QR codes (`app/services/qr_codes.py`) are dynamic: they encode only `/q/<token>`, the target (garden or plant) is resolved by `GET /qr/{token}` and can be changed without reprinting. Public links are built from `PUBLIC_BASE_URL` (`/i/<token>`, `/q/<token>`, `assetlinks.json` in `app/routers/links.py`). Deleted gardens are soft-deleted and purged by `python -m app.jobs.purge` after `GARDEN_RETENTION_DAYS`.

**API layout.** `app/main.py` only builds the app (`create_app(settings)`): it registers exception handlers and includes the per-feature routers in `app/routers/` from an explicit list. `tests/test_routers.py` fails if a router module isn't in that list, unless the module sets `NOT_MOUNTED = "<reason>"` (e.g. `routers/debug.py`, mounted only when `DEBUG_ENDPOINTS` is on, so it doesn't exist in production). Routers stay thin: they declare dependencies and call `app/services/`, which hold the logic and raise domain errors from `app/errors.py` (never `HTTPException`). `app/exception_handlers.py` is the single place those become HTTP responses. Naming: request bodies are `…Request`, responses `…Response` (Pydantic, the API contract), database tables `…Row` (SQLAlchemy); garden approval requests use `Approval…` (e.g. `ApprovalSubmitRequest`) to avoid `RequestRequest`. LLM tool argument schemas keep `…Input`. Config, sessions and the current user come in through `Depends(...)`, so tests swap them with `app.dependency_overrides`. Tests run only on Postgres (the production database), in a `<dev db>_test` database derived from `DATABASE_URL` (override with `TEST_DATABASE_URL`; the name must end in `_test`). The schema is built from the models once per run and tables are truncated before each test. Tests are async (pytest-asyncio, `asyncio_mode = auto`) and call the app through `httpx.AsyncClient` on the test's own event loop; helpers that hit the API or DB are `async` and awaited. Shared test fixtures live in `tests/conftest.py`, helpers in `tests/support.py`. Use `127.0.0.1`, not `localhost`, in Postgres URLs on Windows (IPv6 fallback adds ~20s per connection).

**Convention (see `GardenTender.Api/PLAN.md`).** Don't hand-build features LangChain/LangGraph will later own (streaming, retries, token counting, memory, cross-provider normalization). Keep the seams (`run_chat`, `LlmProvider`, tool registry, `services/`) free of framework dependencies.

**Android.** Single-module Compose app, packaged by feature (`auth/`, `home/`, `qr/`, `settings/`, `chat/`), one screen per file with its ViewModel beside it. Koin DI in `di/AppModule.kt` (inject collaborators; don't read `BuildConfig` or `getSharedPreferences` directly, use `AppConfig` / `SettingsStore`). Routes and the `NavHost` live in `navigation/`; shared UI in `ui/`. Exceptions become user-facing text only in `error/ErrorMessages.kt`; logic layers throw typed errors (e.g. `ChatApiException`).

## Engineering standards (whole repo: API and Android)

- Single responsibility: one feature per router/screen/ViewModel file; no god files (e.g. routes don't accumulate in `main.py`, screens don't accumulate in one file).
- Dependency injection: inject collaborators (FastAPI `Depends`, Koin modules on Android) instead of reaching for globals, so they can be swapped in tests.
- SOLID and DRY: depend on interfaces at the seams (`LlmProvider`, services); extract shared code instead of copying it, including in tests.
- Error handling: raise or return typed domain errors from the logic layer and map them to transport/UI errors in one place; never swallow exceptions silently.
