# GardenTender.Api plan

Python (FastAPI) backend that fronts an LLM for the in-app chat. The LLM can call tools to set reminders, add calendar events and modify app values.

## MVP scope

Get a basic, secure chat loop working with one LLM first; expand afterwards.

- **In:** FastAPI, Auth0 JWT verification and permission checks, `/chat` with a plain provider-agnostic loop (Claude first, iteration cap), a tool registry with `list_plants` and `update_plant` (`confirm`), the same `services/` behind direct endpoints, and the app's `ChatViewModel.reply()` calling `/chat`.
- **Also built (originally deferred):** device tools (`set_reminder` via WorkManager notifications, `add_calendar_event` via the calendar app's insert intent, `confirm` on the latter) and in-memory chat that survives closing the sheet and navigation but is cleared when the app is closed (no on-disk persistence by design). Declining an approval is handled on the device without a network call.
- **Still deferred:** streaming and Ollama (both wait for LangChain), LLM-specific permissions, LangChain/LangGraph.
- **LangChain/LangGraph later:** `/chat` depends only on `run_chat(user, history, decisions)` in `app/llm/loop.py`. A LangGraph agent can replace the inside of that function without touching auth, endpoints, the tool registry (converted to LangChain tools in one place) or `services/`. Consider it when workflows become multi-step or confirmations need durable pause/resume.
- **Stateless confirmation:** `/chat` returns the updated history plus any pending calls; the client sends the history back with `decisions`. A client can forge history, but execution still enforces the same permissions and validation as the direct endpoints, so it gains no extra capability.

## Convention: don't rebuild what LangChain/LangGraph will own

The MVP keeps a thin, replaceable seam instead of custom versions of framework features. When something comes up that LangChain will handle, flag it and leave it out of the MVP (accepting the gap) rather than writing custom code.

Deliberately NOT built in the MVP:
- Provider adapters beyond Claude (no custom Ollama adapter; use `ChatOllama` later)
- Tool-call id generation or message normalization across providers
- A custom streaming event type or stream-chunk assembly (revisit with LangChain's streaming)
- Retry/backoff, token counting, memory/summarization

Kept as the seams to swap later:
- `run_chat(...)` in `app/llm/loop.py`: the only thing `/chat` calls
- `LlmProvider` (one Claude implementation): the point where a LangChain chat model drops in
- Tool registry as plain data (Pydantic input model + handler + permission + `confirm`): converts to LangChain tools in one place
- Handlers know nothing about providers; user and DB session are injected by the caller, never supplied by the model
- Confirmation/resume logic lives only in `loop.py` (LangGraph interrupts would replace it)
- Auth, permissions, `services/` and the DB layer have no LLM-framework dependencies

## Layout

```
GardenTender.Api/
  app/main.py        # FastAPI app, /chat and direct endpoints
  app/auth.py        # JWT verification, require_permission()
  app/services/      # business logic shared by direct endpoints AND tool handlers
  app/tools/         # tool registry: schema, handler, runs_on, permission, confirm
  app/llm/           # provider interface + tool-use loop (see "LLM providers")
    base.py          # LlmProvider protocol
    claude.py        # Claude implementation
    ollama.py        # Ollama implementation (later)
    loop.py          # provider-agnostic tool-use loop
  README.md          # Auth0 setup (below) + run instructions
```

## Authentication

- App sends its Auth0 access token as `Authorization: Bearer ...`.
- API verifies signature (RS256, JWKS at `https://<domain>/.well-known/jwks.json`), `iss`, `aud`, `exp`.
- Requires an Auth0 API with an audience, and the app must request that audience at login (`.withAudience(...)`), otherwise Auth0 issues an opaque token the API cannot verify. Existing users must log in again once.

## Authorization

1. **Permissions:** Auth0 RBAC puts a `permissions` claim in the access token (`chat:use`, `reminders:write`, `calendar:write`, `plants:write`). Endpoints and tools each declare the permission they require.
2. **Roles:** permissions are grouped into roles (`user`, `admin`) in Auth0, not assigned per user.
3. **Ownership:** all data access is scoped by the token's `sub`. The model never supplies a user ID; the server injects it.
4. **Defense in depth:** the model only sees tools the user has permission for; permission is re-checked when a tool call comes back; the app re-validates device tools before executing.
5. **Direct access:** users may call the API directly with the same token. Tool handlers and direct endpoints call the same `services/` functions, so the LLM path adds no capability and bypasses no rule.
6. **The LLM is not an identity.** It has no role and no token. It proposes calls; the API executes them as the user.

## Tool schema and validation

- One schema per tool (name, description, JSON Schema input). The call/result envelope (`id`, `name`, `input` / `tool_result`) is shared, so dispatch is generic.
- Each tool is defined once in the registry as a Pydantic model plus metadata, and the schema, validation and routing all derive from it:

| Field | Meaning |
|-------|---------|
| `schema` | Pydantic input model, exported as JSON Schema for the LLM |
| `handler` | function that performs the action via `services/` |
| `runs_on` | `server` or `device` |
| `permission` | user permission required (checked server-side) |
| `confirm` | whether the user must approve on-device before execution |

- Model output is untrusted. Arguments are validated on the server and re-validated in the app for device tools (same idea as `QrPayload.parse`). Failures return to the model as an error `tool_result` so it can correct itself.
- The system prompt includes current date/time, time zone, and relevant plant data so relative times resolve correctly.

## Per-tool policy

Policy lives in the registry, so the LLM can be limited to less than the user can do without any Auth0 changes.

| Tool | runs_on | permission | confirm |
|------|---------|------------|---------|
| `list_plants` | server | `plants:read` | no |
| `set_reminder` | device | `reminders:write` | no (low risk, easily undone) |
| `add_calendar_event` | device | `calendar:write` | yes |
| `update_plant` | server | `plants:write` | yes for destructive or bulk changes, no for single-field edits |
| `delete_*` | server | `plants:write` | always |

- `confirm` tools return a pending call to the app; the app shows "Add event 'Water ferns' Fri 9am? Confirm / Cancel" and posts the user's decision back. The server does not execute until approved.
- Confirmation also limits prompt-injection damage (e.g. text inside a plant note telling the model to do something).
- The policy table is reviewed whenever a tool is added.

## LLM providers

Start with Claude, move to a local Ollama model later. The provider is swappable and MCP is not required.

- **Interface:** `LlmProvider.chat(messages, tools) -> AssistantTurn`, where a turn is either text or a list of tool calls (`id`, `name`, `input`). `loop.py` owns the tool-use loop (validate, check permission, execute or return a pending `confirm` call, feed the result back) and knows nothing about a specific provider.
- **Schema translation:** the registry stays the single source of truth. Each provider converts it to its own format (Claude: `input_schema`; Ollama/OpenAI-style: `parameters` inside a `function` object). Tool-call and tool-result messages are normalized at the provider boundary.
- **Selection:** provider and model come from config (`LLM_PROVIDER=claude|ollama`, `LLM_MODEL=...`), not code.
- **Ollama notes:**
  - Uses `/api/chat` with a `tools` list and returns `tool_calls`, the same loop as Claude.
  - Pick a model with tool-calling support (e.g. Llama 3.1+, Qwen 2.5+, Mistral) and test it against the tool set before committing.
  - Smaller models are less reliable at tool use: wrong tool, malformed or wrong-typed arguments, repeated calls. Keep schema validation strict, return validation errors to the model as error results, cap loop iterations (e.g. 5), and keep `confirm` on for all writes.
  - Ollama has no authentication and is not an identity. Run it on localhost or a private network reachable only by the API, never from the app or the internet. All Auth0 checks, permissions, `sub` scoping and tool policy remain in the API.
  - Needs a host with enough GPU/RAM for the chosen model; the phone cannot run it.
- **MCP:** not needed for either provider. Only relevant if a chat front-end that speaks MCP is used, or existing MCP servers are reused. An MCP adapter can later wrap the same registry and `services/` layer, with the permission and `confirm` checks enforced server-side.

## Later: LLM-specific permissions

Today the model acts with the user's own permissions, narrowed by per-tool `confirm`. Introduce separate permissions (e.g. `llm:calendar:write`, `llm:plants:write`) only when a trigger below applies.

**When**
- Users should be able to **opt out of AI-driven changes** while still using the app manually.
- You need **admin control** over which accounts or plans get AI actions (free vs paid tiers, beta cohorts).
- AI actions need to be **narrower than manual ones**, e.g. a user may delete plants in the UI but the model must never delete.
- **Audit or compliance** requires distinguishing AI-initiated changes from manual ones.
- A **non-human client** (scheduled agent, third-party integration) starts acting on users' behalf.

**Why**
- Per-tool `confirm` limits damage per call but cannot be turned off per user or revoked centrally.
- Separate permissions give an Auth0-level kill switch (remove the permission or role, no deploy) and a clean answer to "what is the AI allowed to do for this user".

**How**
1. In the Auth0 API, add permissions prefixed `llm:` mirroring the actions to be gated (`llm:reminders:write`, `llm:calendar:write`, `llm:plants:write`).
2. Add them to roles as needed: keep `user` as the default and create e.g. `ai-user` that includes the `llm:*` set. Assign `ai-user` to opted-in users.
3. Add an `llm_permission` field to the tool registry. Tool selection and execution check `llm_permission` in addition to `permission`; direct endpoints keep checking only `permission`.
4. Keep the existing rule that both are required: `llm:*` never grants more than the base permission.
5. Roll out gradually: ship with `llm_permission` defaulting to the existing `permission`, assign `ai-user` to all current users, then tighten roles.
6. Add an in-app toggle that calls the API to grant or revoke `ai-user` (via the Auth0 Management API from the server, never from the app).
7. Tag audit logs with the origin (`llm` or `direct`).

## Later: generative UI with Compose A2UI

Reference: https://developer.android.com/develop/ui/compose/agentic (the page shows the A2UI spec at 0.9.1; library versions and minimum SDK were not listed there, so check before adopting).

- **What it is:** an AndroidX renderer for the A2UI protocol. The agent sends JSON describing a UI, and the app renders it as native Compose. The agent can only use components from a registered catalog, payloads are schema-validated, and user input flows back through two-way bindings. It is not for external agents driving the app, and it has no AppFunctions or MCP side.
- **When to consider it:** after the text chat is stable and a stronger model is in use. Candidates are rich answers (plant cards with water buttons instead of a text list) and replacing the hand-written approve/decline card for `confirm` tools.
- **What it would change:**
  - The server returns a UI description alongside the reply text, and `/chat` passes it through.
  - The app registers a catalog (the Material 3 Basic Catalog or its own) and renders surfaces inside the chat sheet.
  - Button presses (approve, decline, water now) come back as user actions the server maps to `decisions` or tool calls. Permissions, validation and `confirm` stay server-side, never decided by the UI payload.
- **Why not in the MVP:** it adds a protocol layer, small local models like qwen2.5:3b are unlikely to emit valid A2UI reliably, and the API is not yet 1.0.
- **Relation to LangChain:** independent. It is a UI protocol, so it does not fall under the "don't rebuild what LangChain owns" convention.

## Auth0 setup

1. **Create the API:** Dashboard → Applications → APIs → Create API. Name `GardenTender API`, identifier (audience) `https://api.gardentender`, RS256. In Settings enable **RBAC** and **Add Permissions in the Access Token**.
2. **Define permissions** (API → Permissions): `chat:use`, `reminders:write`, `calendar:write`, `plants:read`, `plants:write`.
3. **Create role `user`** (User Management → Roles) with those permissions, and assign it to your account. Auto-assigning on signup needs a post-login Action calling the Management API; do this by hand at first.
4. **Native app:** keep the existing Android application. Confirm callback/logout URLs. In the app, request the audience at login and add it to `BuildConfig` next to `AUTH0_DOMAIN`.
5. **API env vars:**
   ```
   AUTH0_DOMAIN=<tenant>.auth0.com
   AUTH0_AUDIENCE=https://api.gardentender
   ANTHROPIC_API_KEY=...
   ```
   The Anthropic key lives only on the server, never in the APK.
6. **Verify:** log in, decode the access token at jwt.io and check `aud`, `sub`, `permissions`. Then call `/chat` with no token (401), a token without `chat:use` (403) and a valid token (200).

## Build order

Status: steps 1-6 are built; step 7 and streaming wait for LangChain. The Auth0 tenant setup below is manual and not yet done.

1. Scaffold FastAPI, JWT verification, `require_permission`.
2. Service layer and a couple of direct endpoints.
3. Tool registry, `LlmProvider` interface, Claude provider and the tool-use loop (server tools first).
4. App: request audience at login, replace `ChatViewModel.reply()` with an API call.
5. Device tools and the on-device confirmation UI (reminders, then calendar).
6. Chat history is memory-only by design (cleared when the app closes), so no persistence layer is planned. Streaming (SSE) waits for LangChain; the MVP returns the full reply in one response.
7. Ollama: a small temporary hand-written adapter (`app/llm/ollama.py`, non-streaming, generates tool-call ids) was added at the user's request ahead of LangChain. Replace it with `ChatOllama` behind the same seam when LangChain is adopted.
