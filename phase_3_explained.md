# Phase 3 Explained — Session Lifecycle, State Machine & Turn Pipeline

Phase 3 replaced all the hardcoded mock data from Phase 1 with real session management, a full state machine, and a mock-LLM turn pipeline. Every endpoint now delegates to a coordinated set of service classes instead of returning static dictionaries.

---

## Guided walkthrough

### 1. Session Store — `backend/app/core/session_store.py`

The session store is a simple in-memory dictionary that maps session IDs to session data.

```python
class SessionData(BaseModel):
    game_state: GameState
    scenario_package: ScenarioPackage
    turn_index: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

`SessionData` bundles everything a session needs: the mutable `GameState`, the immutable `ScenarioPackage` (the authored scenario files), a `turn_index` counter, and timestamps.

```python
class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}
```

The store itself is just a Python dictionary. `create_session()` generates a UUID, `get_session()` updates `last_accessed_at` each time (for expiry tracking), and `cleanup_expired()` removes sessions that haven't been accessed within a configurable age.

**Why not a database?** For Phase 3, we only need to survive within a single server process. The class is designed so it can be swapped for Redis or a database later — every method takes a session ID and returns data, with no dictionary-specific leaks in the public API.

---

### 2. Progress Models — `backend/app/domain/progress_models.py`

These models define the **contract between the evaluator and the state updater**. In Phase 4 the evaluator will be an LLM; in Phase 3 we use a mock. Either way, the output shape is the same.

```python
class StateEffects(BaseModel):
    unlock_archive: bool = False
    increase_steward_pressure: bool = False
    mark_topic_discovered: str | None = None
```

`StateEffects` is a tiny bag of flags telling the state updater what side-effects to apply. The evaluator decides *intent*, the state updater decides *mechanics*.

```python
class ProgressEvaluatorOutput(BaseModel):
    intent: str                          # "question", "accusation", etc.
    matched_claim_ids: list[str] = []    # which story claims the player touched
    state_effects: StateEffects = StateEffects()
```

The evaluator output says "the player asked a question and matched these claims", and the state updater translates that into flag changes, pressure increments, and gate checks.

---

### 3. Response Models — `backend/app/domain/response_models.py`

These models define the **contract between the constraint builder and the responder**.

```python
class ResponseConstraints(BaseModel):
    may_yield: bool = False
    may_deny: bool = False
    may_deflect: bool = False
    may_hint: bool = False
```

`ResponseConstraints` tells the character responder what it's *allowed* to do. Before the archive is unlocked, the steward can deny and deflect but never yield. After unlock, it flips — the steward must yield.

```python
class TurnResult(BaseModel):
    speaker_type: str       # "narrator" or "character"
    speaker: str            # "Narrator" or "Mr. Hargrove"
    dialogue: str
    location: str
    background_url: str
    portrait_url: str | None
    available_characters: list[str]
    available_exits: list[str]
    suggestions: list[str]
    game_finished: bool
```

`TurnResult` is the **view model** — it contains everything the frontend needs to render one turn. It's the internal equivalent of the DTO, but decoupled from HTTP concerns.

---

### 4. State Updater — `backend/app/services/state_updater.py`

This is the **pure-logic state machine**. It has no side effects, no I/O, no LLM calls. It takes a `GameState` in and returns a new `GameState` out.

#### `apply_progress()` — processing evaluator results

```python
def apply_progress(self, game_state, evaluator_output, scenario_logic):
    flags = game_state.flags.model_copy()
    conv = game_state.conversation_state.model_copy()
    cast = game_state.cast_state.model_copy(deep=True)
```

It starts by copying mutable nested objects. This ensures the original `GameState` is never mutated — we always return a new one.

```python
    # Gate evaluation — check if matched claims satisfy any gate
    matched = set(evaluator_output.matched_claim_ids)
    for gate in scenario_logic.gates:
        required = set(gate.required_claim_ids)
        if required.issubset(matched):
            if gate.effect == "unlock_archive":
                flags.archive_unlocked = True
                cast.steward.yielded = True
```

Gate evaluation uses **set intersection**: convert the list of matched claim IDs to a set, then check if every required claim for a gate is present. `required.issubset(matched)` returns `True` only when all three claims are matched in a single turn. The steward is marked as `yielded` simultaneously.

#### `apply_movement()` — changing locations

```python
def apply_movement(self, game_state, new_location, scenario_logic):
    if new_location not in game_state.available_exits:
        raise ValueError(f"Cannot move to '{new_location}'...")
```

Movement validates against `available_exits` (a `@property` on `GameState` from Phase 2). If the archive is locked, it's not in the exit list, so movement is blocked. After unlock, the archive appears as an exit.

Then it checks end conditions:

```python
    for ec in scenario_logic.end_conditions:
        if ec.trigger == "enter_location" and ec.location == new_location:
            if ec.requires_flag and getattr(flags, ec.requires_flag, False):
                if ec.effect == "game_finished":
                    flags.game_finished = True
```

Entering the archive with `archive_unlocked=True` triggers `game_finished`.

#### `append_turn()` — sliding window history

```python
def append_turn(self, game_state, turn, max_recent=6):
    conv.recent_turns.append(turn)
    if len(conv.recent_turns) > max_recent:
        conv.recent_turns = conv.recent_turns[-max_recent:]
```

This keeps only the last 6 turns. In Phase 4, this recent window is what gets sent to the LLM as conversation context (keeping token costs bounded).

---

### 5. Constraint Builder — `backend/app/services/constraint_builder.py`

A small decision tree that selects which `ConstraintRuleSet` to apply:

```python
def build_constraints(self, game_state, evaluator_output, scenario_logic):
    rules = scenario_logic.constraint_rules
    if game_state.addressed_character == "heir":
        rule_set = rules.heir_default
    elif game_state.flags.archive_unlocked:
        rule_set = rules.steward_after_unlock
    else:
        rule_set = rules.steward_before_unlock
```

The constraint rules come from `logic.json` — they're authored scenario data, not hardcoded logic. This means a different scenario could define completely different constraint progressions.

---

### 6. Session Initializer — `backend/app/services/session_initializer.py`

Orchestrates the three-step process of starting a new game:

```python
def initialize_session(self, scenario_id):
    package = self._loader.load_scenario_package(scenario_id)     # 1. Load files
    errors = validate_scenario_package(package)                    # 2. Validate
    if errors:
        raise ValueError(f"Scenario validation failed: {errors}")
    game_state = GameState(                                        # 3. Build initial state
        location=init.starting_location,
        addressed_character=init.starting_addressed_character,
        ...
    )
    return self._store.create_session(game_state, package)
```

It reads all fields from `initial_state.json` (via the `ScenarioPackage.initial_state` we added in Phase 2) rather than hardcoding them. This means a scenario author can set the starting location, pressure, topics, and cast availability through JSON alone.

---

### 7. Game Service — `backend/app/services/game_service.py`

The central coordinator. Every public method follows the same pattern: **load session → do work → persist → return view model**.

#### Constructor — dependency injection

```python
class GameService:
    def __init__(self, store, initializer, state_updater, constraint_builder):
        self._store = store
        self._initializer = initializer
        self._state_updater = state_updater
        self._constraint_builder = constraint_builder
```

All four dependencies are passed in. This makes testing easy — you can swap any service for a mock.

#### `submit_turn()` — the turn pipeline

This is the core game loop:

```python
def submit_turn(self, session_id, player_input):
    session = self._store.get_session(session_id)     # 1. Load session

    evaluator_output = self._mock_evaluate(...)        # 2. Evaluate (mock)
    gs = self._state_updater.apply_progress(...)       # 3. Update state
    constraints = self._constraint_builder.build(...)  # 4. Build constraints
    dialogue = self._mock_respond(...)                 # 5. Generate response (mock)

    turn_record = TurnRecord(...)                      # 6. Record turn
    gs = self._state_updater.append_turn(gs, turn_record)

    session.turn_index += 1                            # 7. Persist
    self._store.update_session(session_id, gs)

    return self._build_character_turn(gs, pkg, dialogue)  # 8. Return view model
```

Steps 2 and 5 are mocks in Phase 3 — `_mock_evaluate()` returns no claims matched and `_mock_respond()` echoes the player input. Phase 4 will replace exactly these two methods with real LLM calls without changing anything else.

#### Context-sensitive suggestions

```python
@staticmethod
def _suggestions(gs, pkg):
    sug = pkg.prompt_context.suggestions_by_context
    if gs.flags.game_finished:
        return []
    if gs.flags.archive_unlocked:
        return sug.get("post_unlock", [])
    if gs.conversation_state.steward_pressure > 0:
        return sug.get("mid_game", [])
    return sug.get("start", [])
```

The frontend gets different suggested actions based on game progress — this data comes from `prompt_context.json`.

---

### 8. Route Rewiring — `backend/app/api/routes.py`

Phase 1 routes had inline dictionaries:

```python
# Phase 1 (old)
_mock_sessions = {}
MOCK_SESSION_DATA = {"location": "study", ...}

@router.post("/sessions")
async def create_session():
    session_id = str(uuid4())
    _mock_sessions[session_id] = {**MOCK_SESSION_DATA}
    return {...}
```

Phase 3 routes are thin wrappers over `GameService`:

```python
# Phase 3 (new)
@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(svc: GameService = Depends(_get_service)):
    session_id, turn_result = svc.create_session("manor")
    return _turn_result_to_create_response(session_id, turn_result)
```

`Depends(_get_service)` is FastAPI's dependency injection. When a request arrives, FastAPI calls `_get_service()` which returns the `GameService` instance set up during startup. The route handler never creates services — it receives them.

Two mapping functions (`_turn_result_to_create_response` and `_turn_result_to_submit_response`) translate internal `TurnResult` objects into HTTP DTOs. This keeps the domain layer free of HTTP concerns.

---

### 9. Application Wiring — `backend/app/main.py`

```python
store = SessionStore()
loader = ScenarioLoader(base_path=settings.scenario_root_path)
initializer = SessionInitializer(loader=loader, store=store)
state_updater = StateUpdater()
constraint_builder = ConstraintBuilder()
game_service = GameService(store=store, initializer=initializer, ...)
set_game_service(game_service)
```

All service instances are created at module level (when the app starts). The dependency graph is:

```
SessionStore ──┐
               ├──► SessionInitializer ──┐
ScenarioLoader ┘                         │
                                         ├──► GameService
StateUpdater ────────────────────────────┤
ConstraintBuilder ───────────────────────┘
```

`set_game_service()` stores the instance in a module-level variable. `Depends(_get_service)` retrieves it during requests. This "poor man's DI" is simple and works for a single-process server.

---

## Key Concepts and Terminology

### Immutable state transitions

The `StateUpdater` never modifies a `GameState` in place. Instead it calls `model_copy(update={...})`:

```python
return game_state.model_copy(update={"flags": flags, "conversation_state": conv})
```

This creates a **new Pydantic model** with only the changed fields replaced. The original state object is untouched. This pattern makes it easy to reason about what changed and simplifies testing — you can compare before/after snapshots.

### Dependency Injection via `Depends()`

FastAPI's `Depends()` function takes a callable. When a request arrives at a route that uses `Depends(_get_service)`, FastAPI:

1. Sees the parameter `svc: GameService = Depends(_get_service)` in the function signature
2. Calls `_get_service()` to get the value
3. Passes the return value as the `svc` argument

This means route handlers never construct their own services — they declare what they need and FastAPI provides it.

### View models vs domain models vs DTOs

Phase 3 introduces three layers:

| Layer | Example | Purpose |
|-------|---------|---------|
| **Domain model** | `GameState` | Mutable game state — the "truth" |
| **View model** | `TurnResult` | Everything the frontend needs for one turn |
| **DTO** | `CreateSessionResponse` | HTTP-specific shape with serialization rules |

Data flows: `GameState` → `TurnResult` (built by `GameService`) → `CreateSessionResponse` (mapped in routes).

---

## Tradeoffs and Alternatives

| Choice | Why this over alternatives | What we give up |
|--------|---------------------------|-----------------|
| In-memory `dict` store | Simplest possible start; no external dependencies | Sessions lost on restart; no horizontal scaling |
| Module-level global for DI | Avoids framework-level DI container; explicit wiring in `main.py` | Can't easily swap per-request; slightly harder to test at route level |
| `model_copy()` immutable pattern | Easy to reason about; safe to compare before/after | Creates new objects each turn (negligible cost for this scale) |
| Mock evaluator/responder as static methods | Clearly marks what Phase 4 replaces; tests run fast | Tests don't exercise LLM integration — that's Phase 4's job |
| Sliding window for turn history (max=6) | Keeps LLM context bounded; predictable token cost | Older turns are lost — a summary mechanism could help (Phase 4) |
| DTO ↔ TurnResult mapping in routes | Domain layer stays HTTP-agnostic | Two mapping functions to maintain |

---

## Recap

- **Introduced**: Session store, progress/response contracts, state updater (pure-logic state machine), constraint builder, session initializer, game service (turn pipeline coordinator), dependency injection via `Depends()`, route rewiring from mock data to service delegation.
- **Future phases build on**: Phase 4 replaces `_mock_evaluate()` and `_mock_respond()` with real OpenAI calls — the pipeline shape stays identical. Phase 5 adds a frontend that calls these same endpoints. Phase 6 adds tracing around the pipeline steps.
- **Remember**: The `StateUpdater` is pure logic (no I/O) — test it directly. The `GameService` is the integration point — test it with a real `SessionStore` and scenario files. Route handlers should stay thin — if you're putting logic in a route, it belongs in a service.

---

## Review Fixes Applied

### Fix 1 — Reset preserves session identity (High)

`reset_session()` previously deleted the session and called `create_session()`, returning a new UUID. Any client holding the original session ID would get a 404 after reset. Fixed: `reset_session()` now rebuilds a fresh `GameState` from `initial_state` and overwrites the existing session in-place, preserving the original session ID.

### Fix 2 — Session cleanup wired as middleware (High)

`cleanup_expired()` existed on `SessionStore` but was never called. Added an `@app.middleware("http")` in `main.py` that calls `store.cleanup_expired(max_age_minutes=60)` on every request, so stale sessions are reaped during normal traffic.

### Fix 3 — Movement route added (Medium-High)

`handle_movement()` was an internal-only method with no HTTP route. Added `POST /api/sessions/{session_id}/move` with a `MoveRequest` DTO (`target_location` field). Returns `SubmitTurnResponse` (narrator turn) or 422 if the move is invalid.

### Fix 4 — Movement advances turn index and records history (Medium)

`handle_movement()` previously only updated location and persisted, skipping `turn_index` and `append_turn()`. Now records a narrator `TurnRecord` (with `player_input="[move to {location}]"`) and increments `turn_index`, matching the `submit_turn()` contract.

### Fix 5 — Constraints forwarded to mock responder (Medium)

`_mock_respond()` signature now accepts a `ResponseConstraints` parameter. The mock doesn't use it, but the pipeline contract is exercised end-to-end: evaluate → apply_progress → build_constraints → respond(constraints). Phase 4 will forward these constraints into the real LLM prompt.

### Fix 6 — Route no longer reaches into service internals (Low-Medium)

`submit_turn` in `routes.py` previously accessed `svc._store.get_session()` to read `turn_index`. Now `GameService.submit_turn()` returns `tuple[int, TurnResult]` so the route receives `turn_index` through the public API.
