# Implementation Plan

## How this plan is structured

**6 phases, each adding a layer, each producing something runnable.**

Each phase introduces one main technology or concept, builds on the previous, and produces a testable result before moving on. You never write code you can't immediately run and inspect.

| Phase | You learn | Runnable result |
|-------|-----------|-----------------|
| **1. Skeleton + mock vertical slice** | FastAPI basics, Pydantic, project layout, request lifecycle | Hit an endpoint, get a hardcoded game turn back |
| **2. Domain models + scenario loading** | Data modeling, JSON schema design, validation, file I/O | Load the manor package, inspect it via debug endpoint |
| **3. Session + state management** | State machines, in-memory stores, session lifecycle | Create session, submit mock turns, see state change |
| **4. LLM integration** | OpenAI Responses API, structured outputs, prompt composition | Real LLM evaluating input + generating dialogue |
| **5. Game logic wiring** | Full turn pipeline end-to-end | Play the actual game via API (curl/Postman) |
| **6. Frontend** | Vite, DOM rendering, fetch API, SPA patterns | Play in a browser |

### Within each phase

Each step:
- Names the file(s) created or modified
- States what concept/technology it introduces
- Explains the **why** behind the design choice
- Has a concrete **verify** check so you know it works

### Reference

The source of truth for all decisions is `adventure_game_prototype_spec.md`. This plan does not redefine architecture — it sequences the implementation.

---

## Phase 1: Skeleton + mock vertical slice

**Goal:** A running FastAPI server with one endpoint that returns a hardcoded game turn response. You learn the foundational request→response cycle before any real logic exists.

**What you learn:**
- How a Python project is structured (pyproject.toml, packages, modules)
- What FastAPI is and how it handles HTTP requests
- What Pydantic models are and why they matter for request/response validation
- How ASGI servers (Uvicorn) serve Python web apps
- The request → handler → response lifecycle
- How CORS works and why it's needed for frontend-backend separation

---

### Step 1.1 — Project structure and backend package

**Create:**
- `backend/app/__init__.py`
- `backend/app/api/__init__.py`
- `backend/app/core/__init__.py`
- `backend/app/domain/__init__.py`
- `backend/app/services/__init__.py`
- `backend/app/ai/__init__.py`

**Concept:** Python package structure. Each `__init__.py` makes a directory importable. The layered layout (`api/`, `core/`, `domain/`, `services/`, `ai/`) separates concerns by responsibility, not by feature. This is chosen so that each layer has a clear role: `api` handles HTTP, `domain` defines data shapes, `services` holds business logic, `core` holds infrastructure, `ai` wraps external AI calls.

**Why this layout:**
- `api/` — HTTP boundary. Only place that knows about requests/responses.
- `core/` — Infrastructure utilities (config, session store, tracing). No game logic.
- `domain/` — Pure data models. No I/O, no side effects.
- `services/` — Business logic. Orchestrates domain models and AI calls.
- `ai/` — External AI integration. Isolated so the rest of the app doesn't know about OpenAI specifics.

**Verify:** Directories exist and are importable (`python -c "import backend.app"` or similar).

---

### Step 1.2 — Configuration

**Create:** `backend/app/core/config.py`

**Concept:** Centralized configuration via Pydantic `BaseSettings`. Environment variables (from `.env`) are loaded into a typed settings object. This is how FastAPI projects conventionally manage config — no scattered `os.getenv()` calls.

**Contents:**
- `Settings` class with fields: `openai_api_key`, `evaluator_model`, `responder_model`, `scenario_root_path`, `trace_output_path`, `asset_base_url`, `debug`
- `get_settings()` function using `lru_cache` for singleton behavior
- Reads from `.env` file via Pydantic's `model_config` with `env_file`

**Also create:** `.env.example` with placeholder values, `.env` added to `.gitignore`.

**Why typed settings:** Catches misconfiguration at startup instead of at runtime. Pydantic validates types automatically. The `lru_cache` pattern means settings are computed once and reused — a common FastAPI idiom.

**Verify:** `python -c "from backend.app.core.config import get_settings; print(get_settings())"` prints loaded config.

---

### Step 1.3 — Minimal DTOs

**Create:** `backend/app/api/dto.py`

**Concept:** Pydantic models as API contracts. DTOs (Data Transfer Objects) define exactly what the HTTP API accepts and returns. They are separate from internal domain models because the API surface should not leak internal structure.

**Contents (full shape — defined once, used from Phase 1 onward):**
- `CreateSessionResponse` with fields: `session_id: str`, `speaker_type: Literal["narrator"]`, `speaker: str`, `dialogue: str`, `location: str`, `background_url: str`, `portrait_url: str | None`, `available_characters: list[str]`, `available_exits: list[str]`, `suggestions: list[str]`, `game_finished: bool`
- `SubmitTurnRequest` with field: `player_input: str`
- `SubmitTurnResponse` with fields: `session_id: str`, `turn_index: int`, `speaker_type: str`, `speaker: str`, `dialogue: str`, `location: str`, `background_url: str`, `portrait_url: str | None`, `available_characters: list[str]`, `available_exits: list[str]`, `suggestions: list[str]`, `game_finished: bool`
- `SessionStateResponse` with fields: `location: str`, `addressed_character: str`, `flags: dict`, `steward_pressure: int`, `discovered_topics: list[str]`
- `ResetSessionResponse` — same shape as `CreateSessionResponse` (returns full initial scene data, not just a session ID)
- `SwitchCharacterRequest` with field: `character_id: str`

**Why the full shapes up front:** DTO shapes are a contract. Defining them minimal-then-expanding forces later phases to widen the contract, breaking any client code written against the narrow version. By defining the complete shape in Phase 1 and returning hardcoded values for fields you haven't implemented yet, the contract is stable from day one. Mock routes fill unimplemented fields with sensible defaults (`turn_index: 0`, `background_url: ""`, etc.).

**Why separate from domain:** The API contract is a public surface. Internal models may change structure (add fields, rename things) without breaking the HTTP contract. This is a standard practice in layered architectures.

**Verify:** Models can be instantiated and serialized: `SubmitTurnResponse(...).model_dump_json()`. All fields are present even in Phase 1 (some with placeholder values).

---

### Step 1.4 — Routes with hardcoded mock responses

**Create:** `backend/app/api/routes.py`

**Concept:** FastAPI route definitions using `APIRouter`. Each route is a function decorated with `@router.post(...)` or `@router.get(...)`. FastAPI automatically validates request bodies against Pydantic models and serializes responses.

**Contents:**
- `POST /api/sessions` → returns `CreateSessionResponse` with hardcoded scene data
- `POST /api/sessions/{session_id}/turns` → accepts `SubmitTurnRequest`, returns `SubmitTurnResponse` with hardcoded steward dialogue
- `GET /api/sessions/{session_id}/state` → returns a hardcoded `SessionStateResponse`
- `POST /api/sessions/{session_id}/reset` → returns `ResetSessionResponse` with hardcoded initial scene data
- `PUT /api/sessions/{session_id}/addressed-character` → accepts `SwitchCharacterRequest`, returns hardcoded `SessionStateResponse`

**Note on routes vs URLs:** The route definitions in `routes.py` use paths like `/sessions/...` (without `/api`). The `/api` prefix is added in `main.py` when mounting the router (Step 1.5). Throughout this plan, endpoints are shown as their final URL form (`/api/sessions/...`) for consistency.

**Why hardcoded first:** This proves the HTTP layer works in isolation. You can test it with curl or a browser before any real logic exists. Every subsequent phase replaces a hardcoded value with the real implementation.

**Verify:** Each endpoint returns valid JSON with correct status codes.

---

### Step 1.5 — FastAPI app entrypoint

**Create:** `backend/app/main.py`

**Concept:** The FastAPI application factory. Creates the `FastAPI` instance, adds CORS middleware, mounts static files, and includes the API router. This is the single entrypoint Uvicorn uses to serve the app.

**Contents:**
- Create `FastAPI(title="Adventure Game", version="0.1.0")`
- Add `CORSMiddleware` allowing `http://localhost:5173` (Vite dev origin)
- Mount `/assets` as `StaticFiles` directory pointing to the assets folder
- Include router from `routes.py` with prefix `/api`
- No startup logic yet — just wiring

**Why CORS here:** The frontend (Vite on port 5173) and backend (Uvicorn on port 8000) are different origins. Without CORS middleware, the browser blocks cross-origin requests. It's configured narrow (one allowed origin) rather than wildcard for security even in prototype.

**Why static mount:** FastAPI can serve files directly. The `/assets` mount means the frontend can load images like `/assets/scenarios/manor/portraits/steward.png` without a separate file server.

**Verify:** `uvicorn backend.app.main:app --reload` starts without errors. `curl http://localhost:8000/api/sessions -X POST` returns a session ID.

---

### Step 1.6 — pyproject.toml dependencies

**Modify:** `pyproject.toml`

**Concept:** Python dependency management. All runtime dependencies are declared here so `uv sync` installs them into the virtual environment.

**Add dependencies:**
- `fastapi`
- `uvicorn[standard]`
- `pydantic`
- `pydantic-settings`
- `python-dotenv`
- `openai`

**Why `pydantic-settings`:** Separates the settings/config base class from core Pydantic. It handles `.env` file loading.

**Why `openai` now:** We declare it early even though LLM calls come in Phase 4. It avoids a mid-project dependency change.

**Verify:** `uv sync` succeeds. `python -c "import fastapi; print(fastapi.__version__)"` works.

---

### Step 1.7 — Convenience run script

**Create:** `scripts/run_backend.ps1` (Windows PowerShell, since this is a Windows workspace)

**Contents:** Activates venv if needed, runs `uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000`

**Concept:** Developer convenience. A single command to start the backend. The `--reload` flag watches for file changes and auto-restarts — essential during development.

**Verify:** Running the script starts the server and reloads when you edit a Python file.

---

### Phase 1 checkpoint

At this point you have:
- A running FastAPI server
- Working endpoints returning mock data for all routes
- CORS configured for frontend development
- Static file serving mounted
- Typed configuration loading
- Typed API contracts (DTOs) with full shapes defined

You can `curl` every endpoint and see structured JSON responses. The entire HTTP lifecycle works. Everything from here forward is replacing mocks with real implementations.

**Testing (Phase 1):**

**Create:** `tests/conftest.py`, `tests/test_api_smoke.py`

**Add to `pyproject.toml`:** `pytest` and `httpx` as dev dependencies (for FastAPI's `TestClient`).

**Concept:** FastAPI's `TestClient` (backed by `httpx`) lets you make requests to your app without running a server. This is the fastest way to test HTTP behavior.

- `conftest.py`: Create a `client` fixture that yields `TestClient(app)`
- `test_api_smoke.py`: One test per endpoint verifying status code + response shape
  - `test_create_session` → POST `/api/sessions` returns 200, body has `session_id`, `speaker_type`, `dialogue`
  - `test_submit_turn` → POST `/api/sessions/{id}/turns` returns 200, body has all `SubmitTurnResponse` fields
  - `test_get_state` → GET `/api/sessions/{id}/state` returns 200, body has `location`, `flags`
  - `test_reset_session` → POST `/api/sessions/{id}/reset` returns 200, body has same shape as create
  - `test_switch_character` → PUT `/api/sessions/{id}/addressed-character` returns 200
  - `test_invalid_session_404` → GET with a bad session ID returns 404

**Why test now:** These tests validate your DTO contracts. As you replace mocks with real logic in later phases, these tests become regression guards — they catch contract breakage instantly.

**Verify:** `pytest tests/test_api_smoke.py -v` — all pass.

---

## Phase 2: Domain models + scenario loading

**Goal:** Load the manor scenario package from disk into typed Python models. Expose it via a debug endpoint. You learn data modeling, JSON file I/O, and validation.

**What you learn:**
- How Pydantic models represent structured data (domain modeling)
- How JSON files are loaded and validated against schemas
- Difference between authored content (scenario files) and runtime state (GameState)
- Startup validation — catching bad data early
- How a "scenario package" abstraction keeps the runtime generic

---

### Step 2.1 — Scenario JSON files

**Create:**
- `scenarios/manor/story.json`
- `scenarios/manor/characters.json`
- `scenarios/manor/locations.json`
- `scenarios/manor/initial_state.json`
- `scenarios/manor/logic.json`
- `scenarios/manor/assets.json`
- `scenarios/manor/prompt_context.json`

**Concept:** Authored scenario data in JSON. The runtime is generic; the scenario package is what makes it "the manor mystery." Each file has a single responsibility.

**Contents of each file:**

**`story.json`** — Narrative source of truth:
```json
{
  "scenario_id": "manor",
  "title": "The Missing Testament",
  "premise": "You arrive at a manor where an important testament has gone missing. The estate's future hangs in the balance.",
  "story_truth": {
    "hidden_item": "testament",
    "current_holder": "steward",
    "motive": "preserve control over the estate",
    "authority_transfers_to": "heir"
  },
  "ending_summary": "The steward yields under pressure. The archive is opened, the testament is found, and authority passes to the rightful heir."
}
```

**`characters.json`**:
```json
{
  "characters": [
    {
      "id": "steward",
      "name": "Mr. Hargrove",
      "role": "steward",
      "personality": "Formal, guarded, efficient. Maintains composure under pressure but becomes sharper when cornered.",
      "knowledge": "Knows the full truth. Found the testament, read it, hid it to preserve his authority.",
      "portrait_asset": "steward.png"
    },
    {
      "id": "heir",
      "name": "Lady Ashworth",
      "role": "heir",
      "personality": "Direct, observant, increasingly impatient. Suspects foul play but lacks proof.",
      "knowledge": "Does not know the truth as fact. Suspects the steward is deliberately delaying. Cannot prove it.",
      "portrait_asset": "heir.png"
    }
  ]
}
```

**`locations.json`**:
```json
{
  "locations": [
    {
      "id": "study",
      "name": "The Study",
      "description": "A wood-paneled room with tall bookshelves and a broad mahogany desk. Papers are stacked neatly. The steward and heir are both present.",
      "background_asset": "study.png",
      "initially_available": true
    },
    {
      "id": "archive",
      "name": "The Archive Room",
      "description": "A narrow room lined floor to ceiling with document shelves. Dust motes drift in the lamplight. A locked cabinet stands against the far wall.",
      "background_asset": "archive.png",
      "initially_available": false
    }
  ]
}
```

**`initial_state.json`**:
```json
{
  "starting_location": "study",
  "starting_addressed_character": "steward",
  "initial_flags": {
    "archive_unlocked": false,
    "game_finished": false
  },
  "initial_conversation_state": {
    "last_speaker": null,
    "steward_pressure": 0,
    "discovered_topics": [],
    "summary": "",
    "recent_turns": []
  },
  "initial_cast_state": {
    "steward": { "available": true, "yielded": false },
    "heir": { "available": true }
  }
}
```

**`logic.json`** — Generic claim-based progression:
```json
{
  "claims": [
    {
      "id": "claim_steward_possesses_testament",
      "description": "The steward possesses or has found the hidden testament."
    },
    {
      "id": "claim_steward_withholding",
      "description": "The steward is deliberately withholding or hiding the testament."
    },
    {
      "id": "claim_motive_control",
      "description": "The steward's motive is to preserve control over the estate, because the testament transfers authority to the heir."
    }
  ],
  "gates": [
    {
      "id": "archive_unlock",
      "required_claim_ids": [
        "claim_steward_possesses_testament",
        "claim_steward_withholding",
        "claim_motive_control"
      ],
      "effect": "unlock_archive",
      "description": "All three claims must be matched in a single accusation to unlock the archive."
    }
  ],
  "end_conditions": [
    {
      "trigger": "enter_location",
      "location": "archive",
      "requires_flag": "archive_unlocked",
      "effect": "game_finished"
    }
  ],
  "pressure_rules": {
    "min_claims_for_pressure": 1,
    "max_pressure": 2
  },
  "constraint_rules": {
    "steward_before_unlock": {
      "may_yield": false,
      "may_deny": true,
      "may_deflect": true,
      "may_hint": false
    },
    "steward_after_unlock": {
      "may_yield": true,
      "may_deny": false,
      "may_deflect": false,
      "may_hint": false
    },
    "heir_default": {
      "may_yield": false,
      "may_deny": false,
      "may_deflect": false,
      "may_hint": true
    }
  }
}
```

**`assets.json`**:
```json
{
  "portraits": {
    "steward": "scenarios/manor/portraits/steward.png",
    "heir": "scenarios/manor/portraits/heir.png"
  },
  "backgrounds": {
    "study": "scenarios/manor/backgrounds/study.png",
    "archive": "scenarios/manor/backgrounds/archive.png"
  }
}
```

**`prompt_context.json`** — Prompt-support material only (no new truths):
```json
{
  "style_hints": {
    "tone": "gothic manor mystery, restrained and formal",
    "vocabulary": ["testament", "estate", "authority", "archive", "document"],
    "era_feeling": "late Victorian"
  },
  "story_truth_prompt_form": "The steward, Mr. Hargrove, discovered the testament in the archive weeks ago. He read it and learned it transfers full authority over the estate to Lady Ashworth, the heir, effective immediately. He hid the document to preserve his own control. The heir suspects deliberate delay but has no proof.",
  "suggestions_by_context": {
    "start": [
      "Ask the steward about the testament",
      "Ask the heir what she thinks happened",
      "Look around the study"
    ],
    "mid_game": [
      "Confront the steward about the delay",
      "Ask the heir if she trusts the steward",
      "Accuse the steward of hiding the testament"
    ],
    "post_unlock": [
      "Go to the archive"
    ]
  }
}
```

**Why separate files:** Each file has one job. `story.json` is narrative truth, `logic.json` is progression rules, `characters.json` is cast data. This separation means you could swap the logic without touching the story text, or change character names without touching progression rules.

**Why generic claims in `logic.json`:** The evaluator schema uses `matched_claim_ids`, not manor-specific fields. This means the runtime code works for any scenario that defines its own claims and gates. The manor scenario defines 3 claims; a different scenario could define 5 without changing any backend code.

**Verify:** All files are valid JSON and parseable.

---

### Step 2.2 — Scenario domain models

**Create:** `backend/app/domain/scenario_models.py`

**Concept:** Pydantic models that represent the shape of scenario package files. These are the typed Python equivalents of the JSON files. When a JSON file is loaded, it's parsed into these models — if the JSON doesn't match, Pydantic raises a validation error immediately.

**Contents:**
- `StoryTruth` — fields: `hidden_item`, `current_holder`, `motive`, `authority_transfers_to`
- `Story` — fields: `scenario_id`, `title`, `premise`, `story_truth: StoryTruth`, `ending_summary`
- `CharacterDefinition` — fields: `id`, `name`, `role`, `personality`, `knowledge`, `portrait_asset`
- `CharactersFile` — fields: `characters: list[CharacterDefinition]`
- `LocationDefinition` — fields: `id`, `name`, `description`, `background_asset`, `initially_available`
- `LocationsFile` — fields: `locations: list[LocationDefinition]`
- `Claim` — fields: `id`, `description`
- `Gate` — fields: `id`, `required_claim_ids: list[str]`, `effect`, `description`
- `EndCondition` — fields: `trigger`, `location: str | None`, `requires_flag: str | None`, `effect`
- `PressureRules` — fields: `min_claims_for_pressure`, `max_pressure`
- `ConstraintRuleSet` — fields: `may_yield`, `may_deny`, `may_deflect`, `may_hint`
- `ConstraintRules` — fields: `steward_before_unlock`, `steward_after_unlock`, `heir_default`, each `ConstraintRuleSet`
- `ScenarioLogic` — fields: `claims`, `gates`, `end_conditions`, `pressure_rules`, `constraint_rules`
- `AssetManifest` — fields: `portraits: dict[str, str]`, `backgrounds: dict[str, str]`
- `StyleHints` — fields: `tone`, `vocabulary`, `era_feeling`
- `PromptContext` — fields: `style_hints`, `story_truth_prompt_form`, `suggestions_by_context`
- `ScenarioPackage` — aggregates all of the above into one object

**Why Pydantic for domain models:** Pydantic gives you type validation on construction. If a scenario JSON has a typo in a field name or a missing required field, you get a clear error at load time, not a mysterious `KeyError` deep in game logic. This is the "lightweight startup validation" mentioned in the spec.

**Verify:** You can manually instantiate each model from dict literals and they validate correctly. Invalid data raises `ValidationError`.

---

### Step 2.3 — GameState domain model

**Create:** `backend/app/domain/game_state.py`

**Concept:** The authoritative runtime state, separate from scenario definitions. Scenario models describe what's authored; GameState describes what's happening in a live session.

**Contents:**
- `FlagsState` — `archive_unlocked: bool`, `game_finished: bool`
- `TurnRecord` — `player_input: str`, `speaker: str`, `speaker_type: str`, `dialogue: str`
- `ConversationState` — `last_speaker: str | None`, `steward_pressure: int`, `discovered_topics: list[str]`, `summary: str`, `recent_turns: list[TurnRecord]`
- `StewardState` — `available: bool`, `yielded: bool`
- `HeirState` — `available: bool`
- `CastState` — `steward: StewardState`, `heir: HeirState`
- `GameState` — `location: str`, `addressed_character: str`, `flags: FlagsState`, `story_truth: StoryTruth` (reused from scenario), `conversation_state: ConversationState`, `cast_state: CastState`
- Property methods: `available_characters` (derived from location/state), `available_exits` (derived from location/flags)

**Why GameState is separate from scenarios:** A scenario describes what's authored once. GameState is a mutable snapshot of a running session. Many sessions can run the same scenario with different GameStates. This distinction is fundamental to the architecture.

**Why derived properties for available_characters/exits:** These can be computed from the current state — no need to store them separately. This avoids state duplication and possible inconsistency.

**Verify:** Can create a `GameState` from `initial_state.json` values. Derived properties return correct lists.

---

### Step 2.4 — Scenario loader

**Create:** `backend/app/services/scenario_loader.py`

**Concept:** File I/O isolated in one place. Reads JSON files from a scenario package folder and parses them into domain models. The rest of the application never touches the filesystem for scenario data — it receives typed `ScenarioPackage` objects.

**Contents:**
- `ScenarioLoader` class
- `load_scenario_package(scenario_id: str, base_path: Path) -> ScenarioPackage`
- Internal methods: `_load_json(path) -> dict`, `_load_story(...)`, `_load_characters(...)`, etc.

**Why a dedicated loader:** Keeps file I/O concerns out of business logic. If the file format changes (e.g., YAML later), only the loader changes. Services just consume typed models.

**Verify:** `loader.load_scenario_package("manor", Path("scenarios"))` returns a fully populated `ScenarioPackage`. Missing file → clear error.

---

### Step 2.5 — Scenario validators

**Create:** `backend/app/core/validators.py`

**Concept:** Cross-file consistency checks that Pydantic can't express. Pydantic validates each file's shape, but it can't check that `logic.json` references claim IDs that actually exist, or that `assets.json` references character IDs from `characters.json`.

**Contents:**
- `validate_scenario_package(package: ScenarioPackage) -> list[str]` — returns list of validation errors (empty = valid)
- Checks: all claim IDs in gates exist in claims list, all character IDs in assets exist in characters, all location IDs in assets exist in locations, at least one gate defined, starting location exists

**Why not raise exceptions:** Returning a list of errors lets you surface all problems at once, not just the first one. Better developer experience.

**Verify:** Valid manor package → empty list. Deliberately corrupt a reference → error appears in list.

---

### Step 2.6 — Debug endpoint for scenario inspection

**Modify:** `backend/app/api/routes.py`

**Add endpoint:** `GET /api/debug/scenario/{scenario_id}` — loads and returns the full scenario package as JSON.

**Concept:** Debug endpoints let you inspect internal state through the API. This endpoint won't exist in production, but during development it's invaluable for verifying that scenario loading works correctly.

**Verify:** `curl http://localhost:8000/api/debug/scenario/manor` returns the full parsed scenario.

---

### Phase 2 checkpoint

At this point you have:
- 7 authored JSON files defining the manor scenario
- Typed Pydantic models for all scenario data and game state
- A loader that reads files and produces typed objects
- Cross-file validation
- A debug endpoint to inspect the loaded scenario

You understand data modeling, JSON schema design, file I/O, and the distinction between authored content and runtime state.

**Testing (Phase 2):**

**Create:** `tests/test_scenario_models.py`, `tests/test_scenario_loader.py`, `tests/test_validators.py`

**Concept:** Domain models and loaders are pure logic — no HTTP, no LLM. They're the easiest code to unit test and the most rewarding to test early, because malformed data here produces confusing bugs later.

- `test_scenario_models.py`: Validate Pydantic models catch bad data
  - Valid `CharacterDefinition` → no error
  - Missing required field → `ValidationError`
  - `Claim` with empty `id` → catches it (or test that it's allowed, depending on your choice)
  - `Gate` with `required_claim_ids` referencing a valid claim → passes
- `test_scenario_loader.py`: Integration test against real manor scenario files
  - `load_scenario_package("manor")` → returns `ScenarioPackage` with expected counts (2 characters, 2 locations, 3 claims, etc.)
  - Loading a non-existent scenario → raises `FileNotFoundError`
- `test_validators.py`: Cross-file validation
  - Valid manor package → empty error list
  - Package with a gate referencing a non-existent claim → error in list
  - Package with missing starting location → error in list

**Verify:** `pytest tests/test_scenario_models.py tests/test_scenario_loader.py tests/test_validators.py -v` — all pass.

---

## Phase 3: Session + state management

**Goal:** Create sessions, initialize GameState from scenario data, submit mock turns that change state, and observe state transitions. You learn state management, session lifecycle, and the service layer pattern.

**What you learn:**
- In-memory session stores (dictionary-based state keyed by ID)
- Session initialization flow (load scenario → validate → create state)
- The service layer pattern (thin orchestrator between API and domain)
- State updates and how game logic mutates state
- TTL-based cleanup
- How the turn loop works structurally (before LLM calls exist)

---

### Step 3.1 — Session store

**Create:** `backend/app/core/session_store.py`

**Concept:** In-memory dictionary that maps session IDs to session data. This is the simplest possible persistence layer — a Python dict. No database, no file storage. Sessions are lost on restart, which is acceptable for stage 1.

**Contents:**
- `SessionData` dataclass/model: `game_state: GameState`, `scenario_package: ScenarioPackage`, `turn_index: int`, `last_accessed_at: datetime`, `created_at: datetime`
- `SessionStore` class:
  - `_sessions: dict[str, SessionData]`
  - `create_session(game_state, scenario_package) -> str` — generates UUID, stores session, returns ID
  - `get_session(session_id) -> SessionData` — raises if not found, updates `last_accessed_at`
  - `update_session(session_id, game_state)` — replaces state in existing session
  - `delete_session(session_id)`
  - `cleanup_expired(max_age_minutes=60)` — removes sessions older than TTL

**Why a class with methods:** Encapsulates the session dict and provides a clear interface. If you later replace this with Redis or a database, only this file changes.

**Why TTL cleanup:** Prevents unbounded memory growth. Called lazily on new requests or periodically.

**Verify:** Create a session, retrieve it, update it, verify changes persist. Expired sessions are cleaned up.

---

### Step 3.2 — Progress models

**Create:** `backend/app/domain/progress_models.py`

**Concept:** Typed models for evaluator input/output. These are the contract between the evaluator (which will use LLM in Phase 4) and the state updater. Defining them now — before the state updater — ensures the state logic is written against a firm contract, not an implied shape.

**Contents:**
- `StateEffects` — `unlock_archive: bool`, `increase_steward_pressure: bool`, `mark_topic_discovered: str | None`
- `ProgressEvaluatorOutput` — `intent: str`, `target: str | None`, `matched_claim_ids: list[str]`, `matched_gate_condition_ids: list[str]`, `state_effects: StateEffects`, `explanation: str`
- `ProgressEvaluatorInput` — `player_utterance: str`, `visible_scene: str`, `addressed_character: str`, `conversation_summary: str`, `story_truth: StoryTruth`, `flags: FlagsState`, `conversation_state: ConversationState`

**Why models before logic:** The state updater (next step) consumes `ProgressEvaluatorOutput`. By defining the contract first, we can test state transitions independently of LLM behavior. This is the "contract-first" principle — never write code that consumes a shape before that shape is defined.

**Verify:** Can construct `ProgressEvaluatorOutput` with valid and invalid data. Pydantic catches type errors.

---

### Step 3.3 — Response models

**Create:** `backend/app/domain/response_models.py`

**Concept:** Typed models for the responder pipeline and turn output. Like progress models, these are defined before the constraint builder and game service that consume them.

**Contents:**
- `ResponseConstraints` — `may_yield: bool`, `may_deny: bool`, `may_deflect: bool`, `may_hint: bool`
- `CharacterResponderInput` — `speaker: str`, `player_utterance: str`, `intent: str`, `target: str | None`, `matched_claim_ids: list[str]`, `state_snapshot: dict`, `response_constraints: ResponseConstraints`
- `TurnResult` — `speaker_type: str` (`character` | `narrator`), `speaker: str`, `dialogue: str`, `location: str`, `background_url: str`, `portrait_url: str | None`, `available_characters: list[str]`, `available_exits: list[str]`, `suggestions: list[str]`, `game_finished: bool`

**Why `TurnResult`:** This is the view model that the API returns to the frontend. It contains everything the frontend needs to render one turn: dialogue, scene data, available actions, and game state flags.

**Verify:** Models instantiate correctly.

---

### Step 3.4 — State updater (mock evaluator results)

**Create:** `backend/app/services/state_updater.py`

**Concept:** Applies evaluator results to GameState. Now that `ProgressEvaluatorOutput` is defined (Step 3.2), this step implements the pure logic that consumes it. For now, we use hardcoded/mock evaluator results to test state transitions without LLM calls.

**Contents:**
- `StateUpdater` class
- `apply_progress(game_state: GameState, evaluator_output: ProgressEvaluatorOutput, scenario_logic: ScenarioLogic) -> GameState`:
  - Check if `matched_claim_ids` satisfies any gate's `required_claim_ids` → set flag
  - Update `steward_pressure` based on partial claim matches and pressure rules
  - Add to `discovered_topics` if `mark_topic_discovered` effect
  - If gate met: set `archive_unlocked = true`, set `steward.yielded = true`
- `apply_movement(game_state: GameState, new_location: str, scenario_logic: ScenarioLogic) -> GameState`:
  - Change location
  - Check end conditions (entering archive when unlocked → `game_finished = true`)
- `append_turn(game_state: GameState, turn: TurnRecord, max_recent: int = 6) -> GameState`:
  - Append to `recent_turns`, trim to last N

**Why immutable-style updates:** Each method returns a new/updated `GameState`. This makes state transitions explicit and traceable. Nothing mutates state as a side effect — only the state updater does.

**Verify:** Starting from initial state, apply a mock "full accusation" evaluator output → `archive_unlocked` becomes `true`. Apply movement to archive → `game_finished` becomes `true`.

---

### Step 3.5 — Constraint builder

**Create:** `backend/app/services/constraint_builder.py`

**Concept:** Derives what the responder is allowed to do, based on current state, evaluator output, and scenario logic. This is the "control surface" between evaluation and response — the spec's explicit design for preventing the LLM from acting outside its bounds. Depends on both `ProgressEvaluatorOutput` (Step 3.2) and `ResponseConstraints` (Step 3.3).

**Contents:**
- `ConstraintBuilder` class
- `build_constraints(game_state: GameState, evaluator_output: ProgressEvaluatorOutput, scenario_logic: ScenarioLogic) -> ResponseConstraints`:
  - If addressed character is heir → return `heir_default` constraints from logic
  - If steward and `archive_unlocked` → return `steward_after_unlock` constraints
  - Otherwise → return `steward_before_unlock` constraints

**Why a separate builder:** The spec explicitly requires that neither the evaluator nor the responder determine these constraints. A dedicated builder makes this control surface visible and testable.

**Verify:** Before unlock → `may_deny=true, may_yield=false`. After unlock → `may_yield=true, may_deny=false`.

---

### Step 3.6 — Session initializer

**Create:** `backend/app/services/session_initializer.py`

**Concept:** The "prepared session flow." Combines scenario loading, validation, and initial GameState creation into one deterministic sequence. This is the bridge between authored content (scenario files) and runtime state.

**Contents:**
- `SessionInitializer` class (depends on `ScenarioLoader`, `SessionStore`)
- `initialize_session(scenario_id: str) -> str`:
  1. Load scenario package via loader
  2. Validate package via validators
  3. Build initial `GameState` from `initial_state.json` + `story.json`'s `story_truth`
  4. Create session in store with `GameState` + `ScenarioPackage`
  5. Return session ID

**Why a separate initializer:** Session creation is more than "make a dict entry." It involves loading, validating, and deriving initial state. Keeping this logic out of the API route handler keeps routes thin.

**Verify:** `initializer.initialize_session("manor")` returns a session ID. Session store contains a valid `GameState` with `location = "study"`, `archive_unlocked = false`.

---

### Step 3.7 — Game service (mock LLM)

**Create:** `backend/app/services/game_service.py`

**Concept:** The thin coordinator that orchestrates a turn. This is the "main loop" described in the spec. It ties together evaluator → state updater → constraint builder → responder → turn result. In this step, both evaluator and responder are mock implementations.

**Contents:**
- `GameService` class (depends on `SessionStore`, `SessionInitializer`, `StateUpdater`, `ConstraintBuilder`)
- `create_session(scenario_id: str) -> str`
- `get_state(session_id: str) -> GameState`
- `submit_turn(session_id: str, player_input: str) -> TurnResult`:
  1. Get session from store
  2. **Mock evaluator**: return hardcoded `ProgressEvaluatorOutput` with `intent="question"`, no matches
  3. Apply state update
  4. Build constraints
  5. **Mock responder**: return hardcoded dialogue like "The steward regards you coolly."
  6. Append turn to conversation history
  7. Build `TurnResult` with scene data from scenario package
  8. Update session in store
  9. Return `TurnResult`
- `handle_movement(session_id: str, target_location: str) -> TurnResult`:
  1. Validate movement is allowed (check `available_exits`)
  2. Apply movement via state updater
  3. Return narrator `TurnResult` for the transition
- `reset_session(session_id: str) -> TurnResult` — returns full initial scene data, same shape as create

**Why mock LLM here:** The entire turn pipeline is testable without making API calls. You can verify state transitions, constraint derivation, turn history, and narrator triggers by submitting different mock inputs.

**Verify:** Create session → submit turn → get back `TurnResult` with dialogue. State changes are reflected in subsequent `get_state` calls.

---

### Step 3.8 — Wire real routes to game service

**Modify:** `backend/app/api/routes.py` and `backend/app/main.py`

**Concept:** Replace hardcoded route responses with calls to `GameService`. The routes become thin wrappers that convert HTTP DTOs to service calls and service results back to HTTP DTOs.

**Changes:**
- `POST /api/sessions` → calls `game_service.create_session("manor")`
- `POST /api/sessions/{session_id}/turns` → calls `game_service.submit_turn(...)`
- `GET /api/sessions/{session_id}/state` → calls `game_service.get_state(...)`
- `POST /api/sessions/{session_id}/reset` → calls `game_service.reset_session(...)`, returns `ResetSessionResponse` (same shape as `CreateSessionResponse`)
- `PUT /api/sessions/{session_id}/addressed-character` → accepts `{"character_id": "heir"}`, calls `game_service.switch_addressed_character(...)`, returns updated `SessionStateResponse`
- `main.py` instantiates all services and passes them to routes via FastAPI dependency injection

**Why an explicit address-switching endpoint:** The frontend needs to let the player click a character to switch who they're talking to. Rather than overloading the turn-submission endpoint with pattern detection (which is fragile and confusing for beginners), a dedicated endpoint makes this a clean, testable contract. The game service validates that the target character is available at the current location.

**Why dependency injection:** FastAPI's `Depends()` system lets routes declare what they need without constructing it themselves. This makes routes testable (you can inject mocks) and keeps construction logic in one place (`main.py`).

**Verify:** Full round-trip works: create session via API → submit turns → observe state changing → mock dialogue returned. All through HTTP.

---

### Phase 3 checkpoint

At this point you have:
- Session lifecycle: create, use, reset, expire
- GameState that transitions correctly based on evaluator output
- Constraint builder producing correct constraints per state
- A game service coordinating the full turn pipeline (with mock LLM)
- Movement and narrator triggers working
- Real API routes calling real services

You can play through the entire game flow via curl — everything works except the LLM calls are mocked. The architecture is fully wired.

**Testing (Phase 3):**

**Create:** `tests/test_state_updater.py`, `tests/test_constraint_builder.py`, `tests/test_session_store.py`, `tests/test_game_service.py`

**Concept:** State transitions and constraint derivation are deterministic pure logic — the highest-value tests in the project. They verify the game's core rules without any LLM involvement.

- `test_state_updater.py`: Test each state transition in isolation
  - `test_no_matches_no_change` → empty `matched_claim_ids` → state unchanged
  - `test_partial_claims_increase_pressure` → 1 claim matched → `steward_pressure` increments
  - `test_full_accusation_unlocks_archive` → all 3 claims matched → `archive_unlocked = true`, `steward.yielded = true`
  - `test_movement_to_archive_finishes_game` → `apply_movement("archive")` when unlocked → `game_finished = true`
  - `test_movement_blocked_when_locked` → `apply_movement("archive")` when locked → raises or returns error
  - `test_append_turn_trims_to_max` → add 8 turns with `max_recent=6` → only last 6 remain
- `test_constraint_builder.py`: Test constraint derivation per state
  - `test_steward_before_unlock` → `may_deny=true`, `may_yield=false`
  - `test_steward_after_unlock` → `may_yield=true`, `may_deny=false`
  - `test_heir_constraints` → `may_hint=true` always
- `test_session_store.py`: Test session lifecycle
  - `test_create_and_retrieve` → round-trip works
  - `test_unknown_session_raises` → 404-like error
  - `test_cleanup_expired` → old sessions removed, fresh ones kept
- `test_game_service.py`: Integration test with mock LLM (still mocked in Phase 3)
  - `test_full_turn_round_trip` → create session, submit turn, verify `TurnResult` shape
  - `test_reset_returns_initial_state` → reset, verify state matches initial

**Verify:** `pytest tests/ -v` — all tests pass, including Phase 1 and 2 tests (regression).

---

## Phase 4: LLM integration

**Goal:** Replace mock evaluator and responder with real OpenAI Responses API calls. You learn prompt engineering, structured outputs, the Responses API, and how to isolate AI integration.

**What you learn:**
- OpenAI Responses API (distinct from Chat Completions)
- Structured outputs (JSON schema enforcement on LLM output)
- Prompt composition (layered system + task prompts)
- Prompt templates with placeholder substitution
- AI client abstraction (wrapping vendor SDK)
- Retry and fallback patterns

---

### Step 4.1 — AI client wrapper

**Create:** `backend/app/ai/client.py`

**Concept:** A thin wrapper around the OpenAI Python SDK that exposes two methods: one for structured output (evaluator), one for natural text (responder). The rest of the application calls this wrapper, never the OpenAI SDK directly.

**Contents:**
- `AIClient` class
- `__init__(api_key, evaluator_model, responder_model)` — creates `openai.OpenAI` client
- `run_structured(system_prompt: str, user_prompt: str, schema: dict, model: str) -> dict`:
  - Uses the Responses API with `text` format set to `json_schema`
  - Returns parsed JSON dict
- `run_text(system_prompt: str, user_prompt: str, model: str) -> str`:
  - Uses the Responses API with plain text format
  - Returns response text

**Why wrap the SDK:** If OpenAI changes their API, or you switch to Azure OpenAI or Anthropic, only this file changes. Services call `ai_client.run_structured(...)` without knowing what's behind it.

**Why Responses API, not Chat Completions:** The spec explicitly chose this. The Responses API supports structured outputs natively — the model is forced to return valid JSON matching your schema. This is critical for the evaluator, which must return typed progression data, not free text.

**Verify:** A simple test call (e.g., `run_text("You are a helpful assistant", "Say hello")`) returns a string.

---

### Step 4.2 — Prompt templates

**Create:**
- `backend/app/prompts/evaluator/system.txt`
- `backend/app/prompts/evaluator/task.txt`
- `backend/app/prompts/evaluator/output_schema.json`
- `backend/app/prompts/responder/common_system.txt`
- `backend/app/prompts/responder/steward_system.txt`
- `backend/app/prompts/responder/heir_system.txt`
- `backend/app/prompts/responder/task.txt`
- `backend/app/prompts/narrator/scene_transition.txt`
- `backend/app/prompts/narrator/archive_discovery.txt`
- `backend/app/prompts/narrator/ending.txt`

**Concept:** Prompts live in files, not in Python code. This makes them editable without touching code, versionable, and inspectable. Each prompt has a role: system prompts define who the model is, task prompts provide per-turn context.

**Evaluator system prompt** (`evaluator/system.txt`) key instructions:
- You are a game progression evaluator, not a storyteller
- Interpret the player's utterance against the scenario's claims
- Return only structured JSON — never narrative text
- Do not invent new facts; only assess what the player said
- Match claim IDs from the provided list

**Evaluator task template** (`evaluator/task.txt`) with placeholders:
- `{{player_utterance}}`, `{{addressed_character}}`, `{{current_location}}`
- `{{conversation_summary}}`, `{{recent_turns}}`
- `{{story_truth}}`, `{{claims}}`, `{{current_flags}}`

**Evaluator output schema** (`evaluator/output_schema.json`):
- JSON Schema matching `ProgressEvaluatorOutput`
- `intent`: enum of `question`, `accusation`, `inspection`, `statement`, `movement`, `other`
- `matched_claim_ids`: array of strings
- `matched_gate_condition_ids`: array of strings
- `state_effects`: object
- `explanation`: string

**Responder common system** (`responder/common_system.txt`):
- You are a character in a story game
- Speak in character, in first person
- Never invent new world facts
- Never reveal hidden truth unless your constraints allow it
- Obey the response constraints exactly
- Do not decide game progression — that's already been decided

**Steward system** (`responder/steward_system.txt`):
- Character description from scenario
- Defensive posture, formal tone
- When `may_deny`: deflect or deny accusations
- When `may_yield`: admit defeat reluctantly, in character
- Pressure level affects tone (0=calm, 1=tense, 2=cornered)

**Heir system** (`responder/heir_system.txt`):
- Character description from scenario
- Suspicious but lacks proof
- When `may_hint`: can express doubt about steward's motives
- Never states truth as known fact

**Responder task template** (`responder/task.txt`) with placeholders:
- `{{player_utterance}}`, `{{intent}}`, `{{target}}`
- `{{matched_claim_ids}}`, `{{response_constraints}}`
- `{{recent_turns}}`, `{{conversation_summary}}`
- `{{current_location}}`, `{{steward_pressure}}`

**Narrator templates** — static text with minimal placeholders:
- `scene_transition.txt`: "You make your way to {{location_name}}. {{location_description}}"
- `archive_discovery.txt`: longer prose about finding the testament
- `ending.txt`: resolution narration

**Why layered prompts:** The system prompt is stable across turns (defines role). The task prompt changes per turn (provides context). This separation is the "layered prompt composition" from the spec. It keeps prompts maintainable and predictable.

**Verify:** All files exist and contain the expected placeholders.

---

### Step 4.3 — Prompt loader

**Create:** `backend/app/services/prompt_loader.py`

**Concept:** Loads prompt template files from disk at startup and caches them. Like the scenario loader, this isolates file I/O.

**Contents:**
- `PromptLoader` class
- `load_evaluator_templates() -> dict` — returns `{"system": str, "task": str, "schema": dict}`
- `load_responder_templates() -> dict` — returns `{"common_system": str, "steward_system": str, "heir_system": str, "task": str}`
- `load_narrator_templates() -> dict` — returns `{"scene_transition": str, "archive_discovery": str, "ending": str}`

**Verify:** All templates load without error.

---

### Step 4.4 — Prompt builder

**Create:** `backend/app/services/prompt_builder.py`

**Concept:** Takes loaded templates and fills in per-turn context to produce final prompt strings. This is where the layered composition actually happens: base template + scenario context + turn context + constraints.

**Contents:**
- `PromptBuilder` class (depends on loaded templates and scenario's `PromptContext`)
- `build_evaluator_prompt(evaluator_input: ProgressEvaluatorInput, claims: list[Claim]) -> tuple[str, str]`:
  - Returns `(system_prompt, task_prompt)` with all placeholders filled
- `build_responder_prompt(responder_input: CharacterResponderInput, prompt_context: PromptContext) -> tuple[str, str]`:
  - Selects character-specific system prompt
  - Combines with common system prompt
  - Fills task template
  - Returns `(system_prompt, task_prompt)`
- `build_narrator_text(template_key: str, context: dict) -> str`:
  - Simple string substitution on narrator template

**Why a builder, not inline string formatting:** String formatting scattered in 5 different files is unmaintainable. A dedicated builder is testable (feed it inputs, verify the output string), inspectable (you can log the prompt), and the single place where prompt structure is controlled.

**Verify:** Build an evaluator prompt from test inputs → output contains the player utterance and claims list in the right places.

---

### Step 4.5 — Evaluator runner

**Create:** `backend/app/ai/evaluator_runner.py`

**Concept:** Evaluator-specific wrapper that calls the AI client with structured output and parses the result into `ProgressEvaluatorOutput`. Handles retry-once + fallback.

**Contents:**
- `EvaluatorRunner` class (depends on `AIClient`)
- `run(system_prompt: str, task_prompt: str, output_schema: dict) -> ProgressEvaluatorOutput`:
  - Call `ai_client.run_structured(...)` with the evaluator model
  - Parse result into `ProgressEvaluatorOutput`
  - On failure: retry once
  - On second failure: return safe fallback (`intent="other"`, no effects)
  - Log all failures

**Why retry + fallback:** The spec's LLM failure policy. One retry is cheap. The fallback preserves the turn loop — the game doesn't crash, it just treats the input as a non-event.

**Verify:** With a real API key, submit a test utterance and get back a typed evaluator output.

---

### Step 4.6 — Responder runner

**Create:** `backend/app/ai/responder_runner.py`

**Concept:** Responder-specific wrapper for natural text generation. Simpler than the evaluator runner because the output is plain text.

**Contents:**
- `ResponderRunner` class (depends on `AIClient`)
- `run(system_prompt: str, task_prompt: str) -> str`:
  - Call `ai_client.run_text(...)` with the responder model
  - On failure: retry once
  - On second failure: return safe fallback line per speaker

**Verify:** Submit test prompts, get natural dialogue back.

---

### Step 4.7 — Progress evaluator service

**Create:** `backend/app/services/progress_evaluator.py`

**Concept:** The domain-level evaluation boundary. Prepares evaluator input from game state, calls the evaluator runner, and returns typed output. No state mutation here.

**Contents:**
- `ProgressEvaluator` class (depends on `PromptBuilder`, `EvaluatorRunner`)
- `evaluate(player_utterance: str, game_state: GameState, scenario_package: ScenarioPackage) -> ProgressEvaluatorOutput`:
  1. Build `ProgressEvaluatorInput` from game state
  2. Build evaluator prompt via `PromptBuilder`
  3. Call `EvaluatorRunner`
  4. Return result

**Why this service exists between game_service and evaluator_runner:** It translates between the game domain (GameState, ScenarioPackage) and the AI domain (prompts, schemas). The game service shouldn't know about prompt building; the evaluator runner shouldn't know about game state.

**Verify:** End-to-end: game state + player utterance → evaluator prompt → LLM call → typed evaluator output.

---

### Step 4.8 — Character responder service

**Create:** `backend/app/services/character_responder.py`

**Concept:** The domain-level response boundary. Builds responder input, calls the responder runner, returns dialogue.

**Contents:**
- `CharacterResponder` class (depends on `PromptBuilder`, `ResponderRunner`)
- `respond(game_state: GameState, evaluator_output: ProgressEvaluatorOutput, response_constraints: ResponseConstraints, player_utterance: str, scenario_package: ScenarioPackage) -> str`:
  1. Build `CharacterResponderInput`
  2. Build responder prompt via `PromptBuilder`
  3. Call `ResponderRunner`
  4. Return dialogue string

**Verify:** Call with a game state and constraints → get natural in-character dialogue back.

---

### Phase 4 checkpoint

At this point you have:
- A working AI client wrapper for the OpenAI Responses API
- Prompt templates for evaluator, responder, and narrator
- Prompt builder that composes layered prompts
- Evaluator runner with structured output, retry, and fallback
- Responder runner with text output, retry, and fallback
- Domain services bridging game logic and AI calls

All the pieces exist. They haven't been wired into the game service yet — that's Phase 5.

**Testing (Phase 4):**

**Create:** `tests/test_prompt_builder.py`, `tests/test_evaluator_runner.py`

**Concept:** Prompt building is deterministic and highly testable. The evaluator runner's fallback behavior is critical to verify without needing live LLM calls.

- `test_prompt_builder.py`: Test that prompt templates are filled correctly
  - `test_evaluator_prompt_contains_claims` → built prompt includes all claim descriptions
  - `test_evaluator_prompt_contains_player_input` → player utterance appears in task prompt
  - `test_responder_prompt_selects_correct_character` → steward input → steward system prompt used; heir input → heir system prompt used
  - `test_responder_prompt_includes_constraints` → constraints appear verbatim in prompt
- `test_evaluator_runner.py`: Test fallback behavior (mock the AI client)
  - `test_successful_parse` → mock returns valid JSON → `ProgressEvaluatorOutput` with correct fields
  - `test_fallback_on_failure` → mock raises exception → returns safe fallback output (`intent="other"`, no effects)
  - `test_retry_once_before_fallback` → mock fails once then succeeds → returns the success result

**Note:** Tests that hit the real OpenAI API are not included in the automated suite. You can run them manually with a real API key for confidence, but the automated test suite must pass without external dependencies.

**Verify:** `pytest tests/ -v` — all tests pass (no API calls made).

---

## Phase 5: Game logic wiring

**Goal:** Wire everything together so you can play the actual game via API. You learn the full turn pipeline, trace logging, and how all components interact.

**What you learn:**
- How a turn flows end-to-end through the system
- How trace logging provides observability into LLM behavior
- How state transitions drive game progression
- How the narrator handles system events
- The complete gameplay loop from start to archieve unlock to ending

---

### Step 5.1 — Trace logger

**Create:** `backend/app/core/trace_logger.py`

**Concept:** Writes a structured JSON file for each turn, containing the evaluator input/output, responder input/output, state diff, and any errors. This is your primary debugging tool for LLM behavior.

**Contents:**
- `TraceLogger` class
- `write_trace(session_id: str, turn_index: int, trace: dict)`:
  - Writes to `{trace_output_path}/{session_id}/turn_{turn_index}.json` (using the configured `trace_output_path` from settings, not a hardcoded scenario path)
  - Creates directories as needed
- `read_latest_trace(session_id: str) -> dict | None`:
  - Finds the highest-numbered trace file for the session
- Trace payload structure:
  ```
  {
    "turn_index": 3,
    "player_input": "...",
    "evaluator_input": {...},
    "evaluator_output": {...},
    "state_before": {...},
    "state_after": {...},
    "constraints": {...},
    "responder_input": {...},
    "responder_output": "...",
    "errors": []
  }
  ```

**Why traces:** LLM behavior is non-deterministic. When the evaluator misclassifies an input or the responder says something weird, you need to see exactly what prompts were sent and what came back. Traces are the spec's answer to observability.

**Verify:** Submit a turn → trace file appears on disk with all fields populated.

---

### Step 5.2 — Wire game service to real LLM services

**Modify:** `backend/app/services/game_service.py`

**Replace mock implementations with real service calls:**

**Updated `submit_turn` flow:**
1. Get session from store
2. Determine if input is movement ("go to archive") or character interaction
3. **If movement:** validate, apply `state_updater.apply_movement()`, return narrator `TurnResult`
4. **If character interaction:**
   a. Call `progress_evaluator.evaluate(player_input, game_state, scenario_package)`
   b. Call `state_updater.apply_progress(game_state, evaluator_output, scenario_logic)`
   c. Call `constraint_builder.build_constraints(game_state, evaluator_output, scenario_logic)`
   d. Call `character_responder.respond(game_state, evaluator_output, constraints, player_input, scenario_package)`
   e. Call `state_updater.append_turn(game_state, turn_record)`
   f. Update deterministic summary based on discovered topics
   g. Build `TurnResult` with scene data, dialogue, suggestions, asset URLs
   h. Write trace via `trace_logger`
   i. Update session in store
   j. Return `TurnResult`

**Narrator handling:**
- Session creation → return narrator intro text (from `scene_transition.txt` with study description)
- Movement to archive → return narrator text (from `archive_discovery.txt`)
- Game finished → append ending text (from `ending.txt`)

**How `SubmitTurnResponse` DTO is built:**
- `speaker_type` from responder or narrator
- `dialogue` from responder output or narrator template
- `location`, `background_url`, `portrait_url` from scenario assets + current state
- `available_characters` and `available_exits` from game state derived properties
- `suggestions` from `prompt_context.json` based on game phase
- `game_finished` from flags

**Verify:** Play through the entire game via curl:
1. `POST /api/sessions` → get session ID, receive scene intro
2. `POST /api/sessions/{id}/turns` with `{"player_input": "Ask the steward about the testament"}` → steward responds
3. Submit several questions → observe state changes via `GET /api/sessions/{id}/state`
4. Submit a full accusation → `archive_unlocked` becomes true, steward yields
5. Submit `{"player_input": "Go to the archive"}` → narrator describes discovery → `game_finished = true`

---

### Step 5.3 — Trace endpoint

**Modify:** `backend/app/api/routes.py`

**Wire:** `GET /api/sessions/{session_id}/traces/latest` → `trace_logger.read_latest_trace(session_id)`

**Verify:** After submitting turns, the trace endpoint returns the full evaluator/responder/state trace.

---

### Step 5.4 — Input classification (movement vs interaction)

**Modify:** `backend/app/services/game_service.py`

**Add simple movement detection in `submit_turn`:**
- If input matches movement patterns ("go to archive", "move to archive", "enter archive") and the target location is in `available_exits` → delegate to `handle_movement()`
- Otherwise → treat as character interaction with current `addressed_character`

**Note:** Address switching is handled by the dedicated `PUT /api/sessions/{id}/addressed-character` endpoint (wired in Step 3.8), not by text parsing in the turn pipeline. The frontend calls that endpoint when the player clicks a character portrait or name.

**Why simple pattern matching for movement:** Movement detection doesn't need LLM sophistication. A few string patterns suffice. This avoids a third LLM call per turn.

**Verify:** "Go to the archive" triggers movement and narrator response. Regular dialogue goes through the evaluator/responder pipeline.

---

### Phase 5 checkpoint

At this point you have a **fully playable game via API**. The complete pipeline works:
- Player submits free text
- Evaluator interprets it against the scenario's claims
- State updates based on evaluator output
- Constraint builder controls what the responder may do
- Responder generates in-character dialogue
- Narrator handles system events
- Traces record everything
- Game progresses from start → investigation → accusation → unlock → discovery → end

You can play the entire manor scenario from start to finish with curl or Postman.

**Testing (Phase 5):**

**Create:** `tests/test_game_integration.py`

**Concept:** Now that the full pipeline is wired, write integration tests that exercise the complete turn loop via the `TestClient`. These tests use a mocked AI client so they're deterministic and don't require an API key.

- `test_game_integration.py`: Full gameplay loop through HTTP
  - `test_create_session_returns_narrator_intro` → POST create → response has `speaker_type="narrator"`, study scene
  - `test_turn_returns_character_dialogue` → create + submit turn → response has `speaker_type="character"`, `speaker` is a character name
  - `test_full_accusation_unlocks_archive` → create + submit accusation (with mock evaluator returning all claims) → state shows `archive_unlocked=true`
  - `test_movement_after_unlock` → after unlock, submit "go to archive" → narrator response with archive description
  - `test_game_finished_flag` → complete full sequence → `game_finished=true`
  - `test_trace_written` → after a turn, `GET /api/sessions/{id}/traces/latest` returns trace data
  - `test_reset_restores_initial_state` → play some turns, reset, verify state matches initial

**How to mock the AI client:** Create a `FakeAIClient` that returns predetermined responses. Inject it via FastAPI dependency override in the test fixture. This is why the AI client wrapper (Step 4.1) exists — it's the single seam for test substitution.

**Verify:** `pytest tests/ -v` — full suite including all phases passes.

---

## Phase 6: Frontend

**Goal:** A browser UI to play the game. You learn Vite, DOM manipulation, fetch API, and basic SPA patterns.

**What you learn:**
- Vite as a dev server and build tool
- Plain JavaScript DOM rendering (no framework)
- Fetch API for HTTP communication
- Frontend state management (ephemeral view state only)
- CSS layout for a game-like UI
- Proxy configuration for local development

---

### Step 6.1 — Vite project setup

**Create:**
- `frontend/package.json`
- `frontend/vite.config.js`
- `frontend/index.html`

**`package.json`:**
- `name: "adventure-game-frontend"`
- Scripts: `dev`, `build`, `preview`
- Dependencies: `vite` (dev only)

**`vite.config.js`:**
- Dev server on port 5173
- Proxy `/api` and `/assets` to `http://localhost:8000`

**`index.html`:**
- Minimal HTML shell with a root `<div id="app">`
- Script tag pointing to `src/main.js` (type="module")

**Concept:** Vite is a modern dev server that provides hot module reload and builds optimized bundles. The proxy config means the frontend can call `/api/sessions` and Vite forwards it to FastAPI during development — solving the CORS problem at the dev tooling level as well.

**Verify:** `npm install && npm run dev` starts Vite. Browser shows the empty HTML shell.

---

### Step 6.2 — API client

**Create:** `frontend/src/api.js`

**Concept:** A small module of fetch wrappers. All HTTP communication goes through here — no scattered `fetch()` calls elsewhere.

**Contents:**
```javascript
export async function createSession() { ... }
export async function submitTurn(sessionId, playerInput) { ... }
export async function getState(sessionId) { ... }
export async function resetSession(sessionId) { ... }
```

Each function calls the appropriate `/api/...` endpoint, parses JSON, and returns the result. Basic error handling included (throw on non-2xx).

**Why a dedicated API module:** Same reason as the backend's AI client wrapper — isolation. If the API shape changes, only this file changes.

**Verify:** Import in browser console, call `createSession()`, see a session ID returned.

---

### Step 6.3 — View state

**Create:** `frontend/src/state.js`

**Concept:** Frontend-only ephemeral state. This is NOT game truth — it's UI state like "is the input disabled" and "what's the current turn response."

**Contents:**
```javascript
export const state = {
  sessionId: null,
  isSubmitting: false,
  currentTurn: null,   // latest SubmitTurnResponse from backend
  inputText: '',
  errorMessage: null
};
```

**Why explicit view state:** Even without a framework, having one place where UI state lives makes rendering predictable. You always render from `state`, never from scattered variables.

**Verify:** State object is accessible and modifiable.

---

### Step 6.4 — Scene view component

**Create:** `frontend/src/components/scene-view.js`

**Concept:** Renders the background image and character portrait area. Receives scene data from the backend turn response.

**Contents:**
- `renderSceneView(container, turnData)` function
- Sets background image from `turnData.background_url`
- Shows portrait from `turnData.portrait_url`
- Shows location name
- Shows available characters as clickable elements (for address switching)

**Verify:** Passing mock turn data renders background and portrait images.

---

### Step 6.5 — Dialogue panel component

**Create:** `frontend/src/components/dialogue-panel.js`

**Concept:** Renders the dialogue text, speaker name, and text input area. This is the core interaction surface.

**Contents:**
- `renderDialoguePanel(container, turnData, state)` function
- Shows speaker name and dialogue text (styled differently for narrator vs character)
- Text input with placeholder "Ask, inspect, accuse, or tell…"
- Submit button
- Input disabled during `isSubmitting`
- "Thinking…" indicator when submitting

**Verify:** Renders dialogue and a working input field.

---

### Step 6.6 — Prompt suggestions component

**Create:** `frontend/src/components/prompt-suggestions.js`

**Concept:** Three clickable suggestion buttons below the input. Clicking one fills the input field (or submits directly).

**Contents:**
- `renderSuggestions(container, suggestions, onSelect)` function
- Renders up to 3 buttons
- On click, calls `onSelect(suggestionText)`

**Verify:** Suggestions render and clicking one triggers the callback.

---

### Step 6.7 — Renderer

**Create:** `frontend/src/render.js`

**Concept:** Top-level render function that composes scene view, dialogue panel, and suggestions into the app container. Called after every state change.

**Contents:**
- `renderApp(turnData, state)` function
- Calls `renderSceneView`, `renderDialoguePanel`, `renderSuggestions`
- Handles game-finished state (shows ending, disables input)

**Why a top-level renderer:** Without a framework, you need a central place that re-renders the UI. This avoids scattered DOM updates.

**Verify:** Calling `renderApp` with mock data produces the full UI layout.

---

### Step 6.8 — Main entrypoint and event wiring

**Create:** `frontend/src/main.js`

**Concept:** Bootstrap flow. Creates session on load, renders initial scene, wires up input submission events.

**Contents:**
- On load: call `createSession()`, store session ID in state, render initial scene
- On submit: disable input, call `submitTurn(sessionId, inputText)`, update state with response, re-render
- On suggestion click: fill input and submit
- On character click: call `PUT /api/sessions/{id}/addressed-character` with `{character_id}`, re-render with updated state
- On reset: call `resetSession()`, re-render

**Verify:** Full game playable in browser. Create session → see study scene → type input → see steward response → make accusation → archive unlocks → move to archive → game ends.

---

### Step 6.9 — Styling

**Create:** `frontend/src/styles/main.css`

**Concept:** CSS layout for the game UI. The visual design mimics classic dialogue-based adventure games: background fills the scene area, portrait on one side, dialogue panel at the bottom.

**Key layout decisions:**
- Full-height scene area with background image (CSS `background-image`, `cover`)
- Portrait positioned to the side (absolute or flexbox)
- Dialogue panel at the bottom (fixed or flex)
- Input and suggestions below dialogue
- Clear visual distinction between narrator text (italic/different color) and character dialogue
- Loading spinner/text when submitting
- Game-over state styling

**Verify:** The game looks like a visual dialogue scene, not a raw form.

---

### Phase 6 checkpoint

At this point you have a **fully playable game in the browser**:
- Visual scene with background and character portrait
- Dialogue from steward/heir via LLM
- Free text input with suggestions
- Character switching
- Location transitions
- Narrator text for system events
- Full game progression from start to ending

**Testing (Phase 6):**

No automated tests for the frontend in this prototype. The frontend is thin (no framework, no build-time logic). Manual verification via the browser is sufficient at this stage. If you later add frontend complexity, consider adding tests with a lightweight tool like Vitest.

---

## Placeholder assets

At any point during or after Phase 6, placeholder images are needed. For stage 1:

**Create:**
- `assets/scenarios/manor/portraits/steward.png` — any placeholder bust image
- `assets/scenarios/manor/portraits/heir.png` — any placeholder bust image
- `assets/scenarios/manor/backgrounds/study.png` — any placeholder room image
- `assets/scenarios/manor/backgrounds/archive.png` — any placeholder room image

These can be solid color placeholders, free stock images, or generated with the OpenAI image API as a one-time step. The game works without them (just shows broken images), but the visual experience improves substantially with even basic placeholders.

---

## Post-implementation verification checklist

After all 6 phases, verify the complete system by playing through this scenario:

1. **Start game** → See study background, steward portrait, narrator intro text, 3 suggestions
2. **Ask steward about the testament** → Steward gives an evasive answer
3. **Switch to heir** (click or type "ask the heir") → Heir responds with suspicion
4. **Ask heir what she thinks happened** → Heir hints at doubts
5. **Switch back to steward** → Portrait changes
6. **Make an incomplete accusation** ("The steward knows more than he's telling") → Steward deflects. Check state: steward_pressure may increase, but archive stays locked
7. **Make a full accusation** ("You found the testament and hid it because it transfers control to Lady Ashworth") → Steward yields. Check state: `archive_unlocked = true`
8. **"Go to the archive"** appears as suggestion → Click or type it
9. **Narrator describes the discovery** → `game_finished = true`
10. **Game ends** → Input disabled, ending text shown

Also check:
- **Traces**: `GET /api/sessions/{id}/traces/latest` returns evaluator/responder/state data
- **State**: `GET /api/sessions/{id}/state` shows final game state
- **Reset**: `POST /api/sessions/{id}/reset` returns to starting state
- **Errors**: LLM timeout → fallback dialogue appears, game continues

---

## Summary

| Phase | Files created | Key concept | Tests added |
|-------|--------------|-------------|-------------|
| 1 | 8 files + init files | FastAPI, Pydantic, HTTP lifecycle, CORS, static files | API smoke tests (contract guards) |
| 2 | 12 files (7 JSON + 5 Python) | Domain modeling, JSON loading, validation, scenario packages | Model validation, loader, cross-file validator tests |
| 3 | 6 Python files | Sessions, state management, service layer, state transitions | State updater, constraint builder, session store, game service tests |
| 4 | 14 files (10 prompts + 4 Python) | OpenAI API, structured outputs, prompt composition, retry/fallback | Prompt builder, evaluator runner fallback tests |
| 5 | 2 files + modifications | Full pipeline wiring, traces, gameplay loop | Full integration tests (mocked AI client) |
| 6 | 9 files | Vite, DOM rendering, fetch API, SPA patterns | Manual browser verification |

Total: ~51 implementation files + ~8 test files.

Each phase builds on the previous. Each phase produces something you can test — both manually (curl/browser) and with automated tests. By the end, every implementation choice in the spec has a concrete file you can read and understand, and a test that verifies it works.
