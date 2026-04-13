# Phase 1 — Skeleton + Mock Vertical Slice

Phase 1 delivers a running FastAPI server with hardcoded mock endpoints that return the exact DTO shapes the frontend will consume throughout the entire project. Every endpoint works, every response is typed, and the HTTP lifecycle is proven before any game logic exists.

Request validation is exercised (FastAPI + Pydantic reject malformed bodies), and the mock turn endpoint echoes the player’s input to prove request data flows through the handler. Business logic, however, is entirely hardcoded — real evaluation and response generation come in later phases.

---

## Guided Walkthrough

### 1. Project structure (`backend/app/`)

```
backend/
├── __init__.py
└── app/
    ├── __init__.py
    ├── main.py          ← FastAPI app entrypoint
    ├── api/
    │   ├── __init__.py
    │   ├── dto.py       ← Pydantic models for HTTP request/response contracts
    │   └── routes.py    ← Route handlers (mock implementations)
    ├── core/
    │   ├── __init__.py
    │   └── config.py    ← Settings loaded from environment / .env
    ├── domain/
    │   └── __init__.py  ← (empty — filled in Phase 2)
    ├── services/
    │   └── __init__.py  ← (empty — filled in Phase 3)
    └── ai/
        └── __init__.py  ← (empty — filled in Phase 4)
```

Each `__init__.py` file is empty. Its job is to make the directory a Python package so imports like `from backend.app.api.dto import CreateSessionResponse` work. The layout groups files by **responsibility layer**, not by feature:

| Layer | Responsibility | Knows about HTTP? | Knows about OpenAI? |
|-------|---------------|-------------------|---------------------|
| `api/` | HTTP boundary — routes, DTOs | Yes | No |
| `core/` | Infrastructure — config, session store, tracing | No | No |
| `domain/` | Pure data models | No | No |
| `services/` | Business logic orchestration | No | No |
| `ai/` | External AI SDK integration | No | Yes |

This separation means you can test services without a running server, swap the AI provider without touching routes, and change HTTP response shapes without touching game logic.

---

### 2. Configuration — `backend/app/core/config.py`

```python
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    evaluator_model: str = "gpt-4o"
    responder_model: str = "gpt-4o-mini"
    scenario_root_path: Path = Path("scenarios")
    trace_output_path: Path = Path("traces")
    asset_base_url: str = "/assets"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**How it works:**

- `BaseSettings` (from `pydantic-settings`) reads environment variables automatically. A field named `openai_api_key` maps to the env var `OPENAI_API_KEY`. If a `.env` file exists, it's loaded too — that's what `env_file=".env"` does.
- `extra="ignore"` means unknown env vars don't cause errors. Without it, any stray env var would crash startup.
- Every field has a default value, so the app starts even without a `.env` file (useful for tests).
- `@lru_cache` on `get_settings()` means the settings object is created once and reused. Every subsequent call returns the same instance — no re-reading files or env vars.

**Why not `os.getenv()`:** With `os.getenv()` you get strings everywhere, typos fail silently at runtime, and there's no single source of truth for what config the app needs. `BaseSettings` gives you typed fields, validation on startup, and one place to see all config.

---

### 3. DTOs — `backend/app/api/dto.py`

```python
class CreateSessionResponse(BaseModel):
    session_id: str
    speaker_type: Literal["narrator"] = "narrator"
    speaker: str
    dialogue: str
    location: str
    background_url: str
    portrait_url: str | None = None
    available_characters: list[str]
    available_exits: list[str]
    suggestions: list[str]
    game_finished: bool = False
```

DTOs define the **contract** between backend and frontend. `CreateSessionResponse` has every field the frontend will ever need to render the initial scene — even in Phase 1 where most values are hardcoded.

Key design decisions:
- **Full shapes from day one.** The alternative is to start with `session_id` only and add fields later. But that breaks any client code written against the narrow version. By defining everything now, the contract is stable and tests written today still pass in Phase 5.
- **`Literal["narrator"]`** constrains `speaker_type` to exactly the string `"narrator"`. Pydantic enforces this at construction time, not just as documentation.
- **`portrait_url: str | None = None`** — the narrator has no portrait image. The `| None` union type plus a default means the field is optional in the JSON output.
- **`ResetSessionResponse` inherits from `CreateSessionResponse`** — same shape, just a semantic alias. Resets return the full initial scene, not just a status message.

`SubmitTurnResponse` mirrors this shape but adds `turn_index` and allows any `speaker_type` (character or narrator):

```python
class SubmitTurnResponse(BaseModel):
    session_id: str
    turn_index: int
    speaker_type: Literal["character", "narrator"]
    speaker: str
    dialogue: str
    ...
```

`speaker_type` is constrained to `Literal["character", "narrator"]` — Pydantic rejects any other value at construction time. This prevents the mock (or a future service) from returning an unexpected type string.

**Why DTOs are separate from domain models:** The API surface is a public contract. Internal models (like `GameState` in Phase 2) may gain fields, rename things, or restructure without breaking HTTP clients. The DTO layer is the translation boundary.

---

### 4. Routes — `backend/app/api/routes.py`

```python
router = APIRouter()

_mock_sessions: set[str] = set()

def _validate_session(session_id: str) -> None:
    if session_id not in _mock_sessions:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session() -> CreateSessionResponse:
    session_id = str(uuid.uuid4())
    _mock_sessions.add(session_id)
    return CreateSessionResponse(
        session_id=session_id,
        **MOCK_SESSION_DATA,
    )
```

**How it works:**

- `APIRouter()` groups related routes. It's added to the main app with a prefix (`/api`) in `main.py`, so `@router.post("/sessions")` becomes `POST /api/sessions`.
- `response_model=CreateSessionResponse` tells FastAPI to validate the response against this Pydantic model and generate OpenAPI docs from it.
- `_mock_sessions` is a simple in-memory set tracking valid session IDs. `_validate_session()` raises `HTTPException(status_code=404)` for unknown IDs — FastAPI catches this and returns a proper 404 JSON response.
- `**MOCK_SESSION_DATA` spreads a dict of hardcoded values into the constructor. This keeps the mock data in one place.

**The five endpoints:**

| Method | Path (final URL) | Purpose |
|--------|-------------------|---------|
| `POST` | `/api/sessions` | Create a new game session |
| `POST` | `/api/sessions/{id}/turns` | Submit player input, get NPC dialogue back |
| `GET` | `/api/sessions/{id}/state` | Inspect current game state |
| `POST` | `/api/sessions/{id}/reset` | Reset session to initial state |
| `PUT` | `/api/sessions/{id}/addressed-character` | Switch which character the player is talking to |

Each returns hardcoded data now. In Phase 3, the mock responses get replaced by calls to real services. The route definitions themselves don't change — only the body of each handler.

---

### 5. App entrypoint — `backend/app/main.py`

```python
app = FastAPI(title="Adventure Game", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

assets_path = Path("assets")
if assets_path.is_dir():
    app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

app.include_router(router, prefix="/api")
```

**Three things happen here:**

1. **CORS middleware** — The browser enforces same-origin policy. When the frontend (Vite on `localhost:5173`) makes a `fetch()` to the backend (`localhost:8000`), the browser sends a preflight `OPTIONS` request. `CORSMiddleware` responds to that preflight with the right headers so the browser allows the real request. `allow_origins` is narrowly scoped to one origin — not `"*"` — for security.

2. **Static files mount** — `app.mount("/assets", StaticFiles(...))` makes FastAPI serve files from the `assets/` directory. A request to `/assets/scenarios/manor/portraits/steward.png` maps to the file `assets/scenarios/manor/portraits/steward.png` on disk. The `if assets_path.is_dir()` guard prevents a crash when the directory doesn't exist yet (it gets created in Phase 2).

3. **Router inclusion** — `app.include_router(router, prefix="/api")` mounts all routes from `routes.py` under the `/api` prefix. The routes internally define paths like `/sessions/...`, and the final URLs become `/api/sessions/...`.

**Why a factory-style entrypoint:** Uvicorn needs a single `app` object to serve. This file is the one place that wires everything together — middleware, static files, routers. Later phases add startup events and dependency injection here.

---

### 6. Dependencies — `pyproject.toml`

```toml
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "pydantic",
    "pydantic-settings",
    "python-dotenv",
    "openai",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "httpx",
]
```

- **`uvicorn[standard]`** — The `[standard]` extra installs `watchfiles` (for `--reload` file watching) and `httptools` (faster HTTP parsing). Without `[standard]`, auto-reload and performance are worse.
- **`pydantic-settings`** — Split from core `pydantic` since v2. Handles env-var-backed settings specifically.
- **`openai`** — Declared now even though LLM calls come in Phase 4. This avoids a mid-project `uv sync` that changes the lock file while you're working on something else.
- **`httpx`** — Required by FastAPI's `TestClient`. Without it, `TestClient` throws an import error.
- **`pytest`** in dev extras — Not needed at runtime, only for testing.

---

### 7. Tests — `tests/conftest.py` and `tests/test_api_smoke.py`

The shared fixture lives in `tests/conftest.py` (pytest auto-discovers fixtures in this file):

```python
# tests/conftest.py
@pytest.fixture()
def client():
    from backend.app.api.routes import _mock_sessions
    _mock_sessions.clear()
    with TestClient(app) as c:
        yield c
```

The `client` fixture creates a `TestClient` — a test wrapper that makes HTTP requests directly to the FastAPI app without starting a real server. `_mock_sessions.clear()` resets state between tests so they're independent.

```python
def test_create_session(client):
    data = _create_session(client)
    assert "session_id" in data
    assert data["speaker_type"] == "narrator"
    assert isinstance(data["dialogue"], str) and len(data["dialogue"]) > 0
    assert isinstance(data["available_characters"], list)
    ...
```

Each test verifies:
1. **Status code** — the endpoint returns 200 (or 404 for invalid sessions)
2. **Response shape** — required fields exist and have the right types
3. **Contract stability** — field names match what the DTO defines

The `flags` field uses a typed `FlagsResponse` model (not a bare `dict`), so the exact flag names (`archive_unlocked`, `game_finished`) are part of the contract:

```python
class FlagsResponse(BaseModel):
    archive_unlocked: bool = False
    game_finished: bool = False

class SessionStateResponse(BaseModel):
    location: str
    addressed_character: str
    flags: FlagsResponse
    steward_pressure: int
    discovered_topics: list[str]
```

The `switch_character` endpoint validates the requested character against a known set — invalid IDs (like `"stranger"`) are rejected with a 422 error. This bounded validation is what makes the mock a real contract test, not just an echo.

These tests survive into later phases unchanged. When Phase 3 replaces mocks with real services, these same assertions verify the contract wasn't broken.

---

## Key Concepts and Terminology

### Pydantic `BaseModel` vs `BaseSettings`

| | `BaseModel` | `BaseSettings` |
|---|---|---|
| **Purpose** | Define data shapes (DTOs, domain models) | Load configuration from environment |
| **Input source** | Constructor args, dicts, JSON | Environment variables, `.env` files |
| **Used for** | `CreateSessionResponse`, `SubmitTurnRequest` | `Settings` in `config.py` |
| **Validation** | On construction | On construction (from env vars) |

Both validate types. The difference is where the data comes from.

### Route prefix mounting

Routes are defined in `routes.py` with paths like `/sessions`. They're mounted in `main.py` with `prefix="/api"`. The final URL is the concatenation: `/api/sessions`.

```
routes.py:  @router.post("/sessions")       →  defines the handler
main.py:    app.include_router(prefix="/api") →  adds the prefix
Result:     POST /api/sessions               →  what the client calls
```

### `TestClient` — Testing without a server

FastAPI's `TestClient` makes real HTTP requests internally (via ASGI protocol) without starting Uvicorn. It's fast (<100ms to run 6 tests) and deterministic — no network involved.

```python
resp = client.post("/api/sessions")  # No server needed
assert resp.status_code == 200
```

---

## Tradeoffs and Alternatives

| Choice | Why this over alternatives | What we give up |
|--------|---------------------------|-----------------|
| Full DTO shapes in Phase 1 | Contract is stable from day one; tests written now pass in Phase 5 | Mock routes have placeholder values (`background_url: ""`) that look incomplete |
| `_mock_sessions` in-memory set | Simplest possible validation — proves 404 handling works | State is lost on restart; replaced by real session store in Phase 3 |
| `lru_cache` for settings | Singleton without a framework; standard FastAPI pattern | Can't change settings at runtime (not needed for this project) |
| CORS with single allowed origin | Security: only the Vite dev server can call the API | Must update `allow_origins` if the frontend runs on a different port |
| `assets_path.is_dir()` guard | App starts even without assets directory | Assets silently don't mount — no error if you forget to create the directory |
| `openai` dependency in Phase 1 | Avoids mid-project lock file churn | Installs a package that isn't used until Phase 4 |
| Separate `dto.py` from domain models | API surface decoupled from internal structure | Two model files to maintain for similar-looking shapes |

---

## Recap

- **Introduced:** A running FastAPI server with 5 mock endpoints, typed DTOs, centralized config, CORS, static file mounting, and 6 passing smoke tests.
- **Future phases build on:**
  - Phase 2 adds domain models in `domain/` and a scenario loader in `services/` — the `dto.py` shapes don't change.
  - Phase 3 replaces mock route bodies with real service calls — routes.py handlers change, but the DTO contract stays stable.
  - Phase 5 wires the full pipeline — smoke tests still pass because the contracts were defined correctly here.
- **Remember:**
  - Routes in `routes.py` don't have the `/api` prefix — that's added by `main.py`. Always test against `/api/sessions/...`.
  - DTOs are the **only** models the HTTP layer sees. Don't import domain models into `routes.py`.
  - Settings defaults mean the app starts without a `.env` file. If you need an API key (Phase 4), create `.env` from `.env.example`.
