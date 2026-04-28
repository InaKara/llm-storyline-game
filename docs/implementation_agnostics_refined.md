# Scenario Independence — Refined Implementation Plan

## Technology Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Engine scope | **B — Genre-agnostic** |
| 2 | Flag/counter representation | **A1 — `dict[str, bool]` / `dict[str, int]`** |
| 3 | Cast state representation | **B1 — `dict[str, CharacterState]` with `extra: dict[str, Any]`** |
| 4 | Gate effect dispatch | **C2 — Data-driven op list in `logic.json`** |
| 5 | Constraint lookup | **D1 — Ordered condition list, first-match wins** |
| 6 | Asset generation deployment | **Option 3 — Hybrid FastAPI router at `/scenario-builder/`** |
| 7 | Image generation backend | **Local FLUX.1-schnell via HuggingFace `diffusers`** |

Additional: a `docs/image_generation.md` setup guide is included as Step 12.

---

## Step 1 — Generalize `game_state.py`

**Goal:** Remove all character-name-specific typed fields from runtime state models.

**Files affected:** `backend/app/domain/game_state.py`

**Why now:** All downstream services depend on these types. The domain layer must be generalized before any service code changes.

**Changes:**
- Delete `StewardState` and `HeirState` classes
- Add `CharacterState` model: `available: bool = True`, `extra: dict[str, Any] = {}`
- Replace `CastState.steward` and `CastState.heir` typed fields with `characters: dict[str, CharacterState] = {}`
- Replace `FlagsState` typed fields (`archive_unlocked`, `game_finished`) with `flags: dict[str, bool] = {}`
- Remove `ConversationState.steward_pressure`; add `counters: dict[str, int] = {}`
- Update `available_characters` property to iterate `cast_state.characters.items()` and yield character IDs where `state.available is True`
- Update `available_exits` property: flag access changes from `self.flags.archive_unlocked` to `self.flags.flags.get("<flag_name>", False)`; the exits themselves must come from scenario location data rather than being hardcoded — the property should receive (or look up from the loaded scenario) the exits defined in `locations.json`

---

## Step 2 — Generalize `scenario_models.py`

**Goal:** Remove all character-name-specific fields from authored scenario shapes — the Pydantic models that validate JSON loaded from disk.

**Files affected:** `backend/app/domain/scenario_models.py`

**Why now:** `ScenarioLoader` uses these models to parse scenario JSON. The loader must understand the new schema before anything else loads a scenario.

**Changes:**
- Delete `InitialStewardState` and `InitialHeirState` classes
- Replace `InitialCastState.steward`, `.heir` with `characters: dict[str, dict[str, Any]]`
- Replace `InitialFlags.archive_unlocked`, `.game_finished` with `flags: dict[str, bool]`
- Replace `InitialConversationState.steward_pressure` with `counters: dict[str, int]`
- Add `ConditionExpr` model: `flag: str`, `value: bool` (extensible later for counter conditions)
- Add `ConstraintRule` model: `character_id: str`, `condition: ConditionExpr | None`, `constraints: dict[str, bool]`
- Replace `ConstraintRules` (with character-named fields `steward_before_unlock`, `steward_after_unlock`, `heir_default`) with `constraint_rules: list[ConstraintRule]` directly on the logic model
- Add `EffectOp` model: `op: str`, `key: str | None = None`, `character: str | None = None`, `value: Any = None`
- Update `Gate` model: `effect` field type changes from `str` to `list[EffectOp]`
- Update `EndCondition` model: `effect` field type changes from `str` to `list[EffectOp]`
- Remove or deprecate `PressureRules` (pressure is now a generic counter)

---

## Step 3 — Migrate `manor` scenario JSON to generic schema

**Goal:** Verify that the new domain models load the existing manor scenario without data loss. All existing tests should still pass after this step.

**Files affected:**
- `scenarios/manor/initial_state.json`
- `scenarios/manor/logic.json`

**Why now:** JSON migration confirms the new schema shape is correct before any service code changes. Running existing tests against the migrated JSON is the fastest validation.

**Changes to `initial_state.json`:**
- Rename top-level key `initial_flags` → keep name but change value from typed fields to a plain dict: `{ "archive_unlocked": false, "game_finished": false }`
- Rename `initial_conversation_state.steward_pressure` → move to `initial_counters: { "steward_pressure": 0 }` (or a `counters` key inside `initial_conversation_state`)
- Replace `initial_cast_state: { "steward": {...}, "heir": {...} }` with `characters: { "steward": { "available": true, "extra": { "yielded": false } }, "heir": { "available": true, "extra": {} } }`

**Changes to `logic.json`:**
- Replace the `constraint_rules` object (with `steward_before_unlock`, `steward_after_unlock`, `heir_default` keys) with an ordered list following D1 format:
  ```
  # steward rule when archive is locked
  { "character_id": "steward", "condition": { "flag": "archive_unlocked", "value": false }, "constraints": { "may_yield": false, "may_deny": true, "may_deflect": true, "may_hint": false } }
  # steward rule when archive is unlocked
  { "character_id": "steward", "condition": { "flag": "archive_unlocked", "value": true }, "constraints": { "may_yield": true, "may_deny": false, "may_deflect": false, "may_hint": false } }
  # heir default (no condition)
  { "character_id": "heir", "condition": null, "constraints": { "may_yield": false, "may_deny": false, "may_deflect": false, "may_hint": true } }
  ```
- Replace `gate.effect: "unlock_archive"` string with op list:
  ```
  [
    { "op": "set_flag", "key": "archive_unlocked", "value": true },
    { "op": "set_character_state", "character": "steward", "key": "yielded", "value": true }
  ]
  ```
- Replace end condition effect strings (e.g. `"game_finished"`) with op lists: `[{ "op": "set_flag", "key": "game_finished", "value": true }]`

---

## Step 4 — Update `constraint_builder.py`

**Goal:** Remove hardcoded character names and typed flag attribute access; implement D1 ordered condition list evaluation.

**Files affected:** `backend/app/services/constraint_builder.py`

**Why now:** Domain models are now generic; services can be updated to use them.

**Changes:**
- Remove `if game_state.addressed_character == "heir"` and all named-rule lookups (`rules.heir_default`, `rules.steward_before_unlock`, `rules.steward_after_unlock`)
- Add D1 evaluation loop: iterate `constraint_rules` list; for each rule:
  - If `rule.character_id != game_state.addressed_character`: skip
  - If `rule.condition is None`: match (default)
  - If `rule.condition` is present: evaluate `game_state.flags.flags.get(rule.condition.flag, False) == rule.condition.value`
  - Return `rule.constraints` on first match
- Return an empty/default constraints dict if no rule matches
- Return type changes from a typed `ConstraintRules` field accessor to `dict[str, bool]`

---

## Step 5 — Update `state_updater.py`

**Goal:** Replace string-matching gate effect dispatch with C2 op-list interpreter.

**Files affected:** `backend/app/services/state_updater.py`

**Why now:** Gate models now carry `list[EffectOp]` instead of a string; the updater must interpret them.

**Changes:**
- Delete `if gate.effect == "unlock_archive": flags.archive_unlocked = True` and all equivalent hardcoded branches
- Add `_apply_ops(ops: list[EffectOp], game_state: GameState) -> None` function that dispatches on `op.op`:
  - `"set_flag"` → `game_state.flags.flags[op.key] = op.value`
  - `"set_counter"` → `game_state.conversation_state.counters[op.key] = op.value`
  - `"increment_counter"` → `game_state.conversation_state.counters[op.key] = game_state.conversation_state.counters.get(op.key, 0) + 1`
  - `"set_character_state"` → `game_state.cast_state.characters[op.character].extra[op.key] = op.value`
  - `"set_character_available"` → `game_state.cast_state.characters[op.character].available = op.value`
  - Unknown op: log a warning, do not raise (resilience for future ops)
- Call `_apply_ops(gate.effect, game_state)` for gate effects and `_apply_ops(end_condition.effect, game_state)` for end conditions

---

## Step 6 — Update `game_service.py`

**Goal:** Remove all hardcoded character/flag attribute references from game initialization and status logic.

**Files affected:** `backend/app/services/game_service.py`

**Changes:**
- Remove `from ... import HeirState, StewardState`
- Replace character-specific `CastState(steward=StewardState(...), heir=HeirState(...))` initialization with a generic construction: iterate `scenario.initial_state.characters` dict to build `CastState(characters={...})`
- Replace `gs.flags.game_finished` with `gs.flags.flags.get("game_finished", False)`
- Replace `gs.flags.archive_unlocked` with `gs.flags.flags.get("archive_unlocked", False)`
- Replace `gs.conversation_state.steward_pressure` with `gs.conversation_state.counters.get("steward_pressure", 0)`
- Replace hardcoded narrator template key `"archive_discovery"` with a generic key looked up from scenario config (e.g. from a new `narrator_events` section in `prompt_context.json` or `logic.json`)
- Replace literal `"You enter the archive."` with narrator template content fetched by that generic key

---

## Step 7 — Update API DTOs and routes

**Goal:** Expose generic `flags: dict[str, bool]` and `counters: dict[str, int]` in the API response instead of hardcoded named fields.

**Files affected:**
- `backend/app/api/dto.py`
- `backend/app/api/routes.py`

**Note:** This is a breaking API change. Frontend code that reads `FlagsDTO.archive_unlocked` or `GameStatusDTO.steward_pressure` by name must be updated in the same step or immediately after.

**Changes to `dto.py`:**
- Replace `FlagsDTO.archive_unlocked: bool`, `.game_finished: bool` with `flags: dict[str, bool]`
- Replace `GameStatusDTO.steward_pressure: int` with `counters: dict[str, int]`

**Changes to `routes.py`:**
- Replace `gs.flags.archive_unlocked`, `gs.flags.game_finished` with `gs.flags.flags`
- Replace `gs.conversation_state.steward_pressure` with `gs.conversation_state.counters`

**Frontend changes (same step):**
- Update any frontend code that reads `response.flags.archive_unlocked` to use `response.flags["archive_unlocked"]` or equivalent dict access pattern
- Update any frontend code that reads `response.steward_pressure` to use `response.counters["steward_pressure"]`

---

## Step 8 — Update/rewrite tests

**Goal:** All tests pass against the new generic schemas. No test file should reference `StewardState`, `HeirState`, typed flag fields, or character-specific attribute access.

**Files affected:** `tests/conftest.py`, `tests/test_*.py` (all)

**Changes:**
- Update `conftest.py` fixtures: build `GameState` using generic `CastState(characters={...})`, `FlagsState(flags={...})`, `ConversationState(counters={...})`
- Update all test assertions that access `.steward_pressure`, `.archive_unlocked`, `.game_finished` as attributes — change to dict access
- Update mock scenario JSON in fixtures to use D1 constraint list format and C2 op-list effect format
- Update `test_constraint_builder.py`: assertions use `dict[str, bool]` return instead of named attribute access on a `ConstraintRules` object
- Update `test_state_updater.py`: gate and end condition fixtures use `list[EffectOp]` instead of string effect names
- Update `test_game_service.py`: remove any `StewardState`/`HeirState` construction

---

## Step 9 — Implement `ScenarioGenerator` service (text assets)

**Goal:** A service class that accepts a story brief and generates all text-based scenario JSON files in the correct dependency order.

**Files affected (new):**
- `backend/app/services/scenario_generator.py`
- `backend/app/api/scenario_builder_routes.py`
- Register router in `backend/app/main.py` (or equivalent app factory) at prefix `/scenario-builder`

**Approach:**
- `ScenarioGenerator` class with async methods for each asset, following the dependency order from section 5.3 of `implementation_agnostics.md`:
  1. `generate_story(brief: str) -> StoryJSON`
  2. `generate_characters(story: StoryJSON) -> CharactersJSON`
  3. `generate_locations(story, characters) -> LocationsJSON`
  4. `generate_logic(story, characters, locations) -> LogicJSON` — must produce D1 constraint list and C2 op-list effects
  5. `generate_initial_state(characters, locations, logic) -> InitialStateJSON` — must produce generic flags/counters/characters dicts
  6. `generate_prompt_context(story, characters) -> PromptContextJSON`
  7. `generate_assets_manifest(characters, locations) -> AssetsJSON`
  8. `generate_character_system_prompts(characters, story) -> dict[str, str]`
  9. `generate_narrator_templates(story, locations) -> dict[str, str]`
- Each method calls the LLM using the OpenAI client (or a LM Studio-compatible endpoint — same API shape, configurable base URL via env var `LLM_BASE_URL`)
- Each method uses structured output: `response_format={"type": "json_schema", "json_schema": ...}` or Pydantic `response_format` with `model.model_json_schema()`
- Each method validates the LLM response with the corresponding Pydantic model before returning
- Each method writes its output to `scenarios/{scenario_id}/` before returning (allowing human review between steps)
- `ScenarioBuilder` FastAPI router at `/scenario-builder/` with:
  - `POST /scenario-builder/generate` — accepts `{ "scenario_id": str, "brief": str }`, runs full generation pipeline, returns summary
  - `POST /scenario-builder/generate-step` — accepts `{ "scenario_id": str, "step": str }` for step-by-step generation
  - `GET /scenario-builder/scenarios` — list available scenario IDs on disk

---

## Step 10 — Implement image generation service

**Goal:** A service that generates character portraits and location backgrounds using FLUX.1-schnell locally via HuggingFace `diffusers`, with a CLI entrypoint for manual testing.

**Files affected (new):**
- `backend/app/services/image_generator.py`
- `tools/generate_images.py` (CLI entrypoint)

**Approach:**
- `ImageGenerator` class:
  - Constructor: loads `FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16)` and moves to CUDA; pipeline is lazy-loaded on first use to avoid startup overhead
  - `generate_portrait(visual_description: str, character_id: str, scenario_id: str) -> Path`: builds a portrait-specific prompt, calls `pipeline(prompt, ...)`, saves to `assets/scenarios/{scenario_id}/portraits/{character_id}.png`
  - `generate_background(description: str, style_hints: str, location_id: str, scenario_id: str) -> Path`: builds a background-specific prompt, saves to `assets/scenarios/{scenario_id}/backgrounds/{location_id}.png`
  - Both methods accept optional `seed: int` for reproducibility
- Image generation added to `ScenarioGenerator.generate_all()` after text assets are complete (steps 10 and 11 in section 5.3): portraits and backgrounds generated in parallel using `asyncio.gather` with a thread pool executor (since `diffusers` is synchronous)
- CLI (`tools/generate_images.py`) uses `argparse`:
  - `--scenario <id>` (required)
  - `--type portrait|background|all` (required)
  - `--id <character_or_location_id>` (for single item generation)
  - `--seed <int>` (optional)
  - Example: `python tools/generate_images.py --scenario manor --type portrait --id steward`

**Dependencies to add to `pyproject.toml`:**
- `diffusers >= 0.30`
- `torch >= 2.3` (with CUDA extra: `torch[cuda]` or manual CUDA wheel)
- `accelerate`
- `transformers`
- `sentencepiece` (required by some FLUX tokenizers)

---

## Step 11 — Wire image generation into `/scenario-builder/` API

**Goal:** The `/scenario-builder/generate` endpoint triggers image generation after text assets are complete.

**Files affected:**
- `backend/app/services/scenario_generator.py` (update `generate_all()`)
- `backend/app/api/scenario_builder_routes.py` (update generate endpoint)

**Changes:**
- `ScenarioGenerator.generate_all()`: after all text assets are written to disk, call `ImageGenerator` for each character portrait and each location background
- Add `POST /scenario-builder/generate-images` endpoint that generates only images for an already-existing scenario (useful for regenerating with different seeds)
- Add progress/status tracking if running the full pipeline synchronously proves too slow for a single HTTP request — consider running as a background task (`BackgroundTasks`) and returning a job ID immediately

---

## Step 12 — Create `docs/image_generation.md` setup guide

**Goal:** Document how to install and configure FLUX.1-schnell for local generation on the target hardware (RTX 4060 Laptop, 8 GB VRAM).

**Files affected (new):** `docs/image_generation.md`

**Contents:**
- Hardware requirements (minimum VRAM, CUDA version)
- Python and CUDA prerequisites (CUDA Toolkit version, `nvcc` check)
- Step-by-step `pip install` commands for `torch`, `diffusers`, `accelerate`, `transformers`
- Model download: how `from_pretrained` downloads and caches FLUX.1-schnell (~24 GB full, ~6 GB bfloat16)
  - Alternative: manual download from HuggingFace Hub using `huggingface-cli`
- Memory optimization settings for 8 GB VRAM (e.g. `enable_model_cpu_offload()`, `enable_sequential_cpu_offload()`, `torch.bfloat16`)
- How to test with CLI: example commands for portrait and background generation
- How to verify GPU is being used (`torch.cuda.is_available()`)
- Common issues and fixes: driver version mismatches, OOM errors, slow first-run (model loading)
- Note on FLUX.1-schnell licence (Apache 2.0 — commercial use permitted)

---

## Implementation Order Summary

| Step | Change | Blocked on |
|------|--------|-----------|
| 1 | Generalize `game_state.py` | — |
| 2 | Generalize `scenario_models.py` | Step 1 |
| 3 | Migrate manor JSON | Steps 1–2 |
| 4 | Update `constraint_builder.py` | Steps 1–3 |
| 5 | Update `state_updater.py` | Steps 1–3 |
| 6 | Update `game_service.py` | Steps 1–5 |
| 7 | Update API DTOs and routes | Step 6 |
| 8 | Update/rewrite tests | Steps 1–7 |
| 9 | Implement `ScenarioGenerator` | Steps 1–2 |
| 10 | Implement `ImageGenerator` + CLI | Step 9 (for integration); can start independently |
| 11 | Wire images into `/scenario-builder/` | Steps 9–10 |
| 12 | Write `image_generation.md` | Step 10 |
