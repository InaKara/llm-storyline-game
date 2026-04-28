# Scenario Independence Implementation Plan

## Status: Planning — Decisions Required

This document maps every point where the current codebase is coupled to the `manor` scenario, catalogues the concept abstractions needed for a generic engine, and presents alternative implementation paths at each decision point.

**The reader must make a choice wherever a `[DECISION]` marker appears before implementation can begin.**

---

## 1. Scope Options

Two interpretations of "scenario-agnostic" are possible. This affects the depth of every subsequent redesign.

### Option A — Same-genre engine (mystery/detective)

The engine remains a mystery investigation game. Different stories have different characters, locations, items, and clues — but the mechanical skeleton (player interrogates characters, makes accusations, gates unlock, game ends) stays fixed.

**Implications:**
- Most current domain models are re-usable if field names are generalized.
- Gate evaluation, constraint lookup, and pressure tracking remain as concepts — only their names and values become data-driven.
- Asset generation produces: story JSON, character portraits, location backgrounds, prompt templates.

**Pros:** Lower risk; faster to implement; existing test coverage remains largely valid.  
**Cons:** Cannot support a fundamentally different mechanic (e.g. a trading game, a stealth game).

---

### Option B — Genre-agnostic engine

The engine becomes a generic narrative game host. Mechanics (what counters exist, what gate effects can do, what constraints characters have) are entirely defined by the scenario files.

**Implications:**
- `StateEffects`, `FlagsState`, `ConstraintRules` must be replaced with generic key-value registries loaded from JSON.
- Gate effects become a data-driven dispatch table, not an `if gate.effect == "unlock_archive"` check.
- Constraint fields (`may_yield`, `may_deny`, …) become a named boolean dict, not a Pydantic model with fixed fields.
- Substantially more runtime reflection is needed.

**Pros:** Full flexibility; one engine could run any authored narrative scenario.  
**Cons:** Higher complexity; current tests require significant rewrite; harder to validate LLM output against a generic schema.

---

**[DECISION 1] Choose scope: Option A (same-genre) or Option B (genre-agnostic)?**

*The rest of this document describes both paths in parallel where they diverge.*

---

## 2. Inventory of Hardcoded Violations

All violations are in `.py` files unless noted.

### 2.1 Domain Models (`backend/app/domain/`)

#### `game_state.py`

| Location | Violation | Fix needed for |
|----------|-----------|----------------|
| `StewardState`, `HeirState` classes | Character-specific Python classes | A and B |
| `CastState.steward`, `CastState.heir` typed fields | Character names as typed fields | A and B |
| `available_characters` property | Hardcodes `cast_state.steward.available`, `cast_state.heir.available` | A and B |
| `available_exits` property | Hardcodes `location == "study"`, `flags.archive_unlocked`, location string `"archive"` | A and B |
| `FlagsState.archive_unlocked`, `FlagsState.game_finished` | Scenario-specific flag names as typed fields | A and B |
| `ConversationState.steward_pressure` | Character-specific counter as a typed field | A and B |

#### `scenario_models.py`

| Location | Violation | Fix needed for |
|----------|-----------|----------------|
| `InitialStewardState`, `InitialHeirState` classes | Character-specific authored state shapes | A and B |
| `InitialCastState.steward`, `.heir` | Character names as typed fields | A and B |
| `InitialFlags.archive_unlocked`, `.game_finished` | Scenario-specific flag names as fixed fields | A and B |
| `InitialConversationState.steward_pressure` | Character-specific counter in authored state | A and B |
| `ConstraintRules.steward_before_unlock`, `.steward_after_unlock`, `.heir_default` | Character and state names as typed fields | A and B |
| `PressureRules` class (docstring + concept) | "Steward pressure" concept leaked into a generic type name | A: rename/generalize / B: remove, replaced by generic counter |

#### `progress_models.py`

| Location | Violation | Fix needed for |
|----------|-----------|----------------|
| `StateEffects.unlock_archive` | Scenario-specific effect name as typed field | A: generalize / B: replace with dict |
| `StateEffects.increase_steward_pressure` | Character-specific counter effect as typed field | A: generalize / B: replace with dict |

#### `response_models.py`

| Location | Violation | Fix needed for |
|----------|-----------|----------------|
| `ResponseConstraints.may_yield`, `.may_deny`, `.may_deflect`, `.may_hint` | Scenario-specific constraint names as typed fields | A: keep names, add extensibility / B: replace with `dict[str, bool]` |

---

### 2.2 Service Logic (`backend/app/services/`)

#### `constraint_builder.py`

| Location | Violation | Fix needed for |
|----------|-----------|----------------|
| `game_state.addressed_character == "heir"` | Character name as string literal | A and B |
| `game_state.flags.archive_unlocked` | Flag name as attribute access | A and B |
| `rules.heir_default`, `rules.steward_before_unlock`, `rules.steward_after_unlock` | Character-keyed constraint lookup | A and B |

#### `state_updater.py`

| Location | Violation | Fix needed for |
|----------|-----------|----------------|
| `if gate.effect == "unlock_archive"` | Hardcoded gate effect string matched with `==` | A: effect dispatch table / B: data-driven ops |
| `flags.archive_unlocked = True` | Flag name as attribute access | A and B |
| `cast.steward.yielded = True` | Character name as attribute access | A and B |
| `conv.steward_pressure` (read and write) | Counter name as attribute access | A and B |
| `if ec.effect == "game_finished"` | Hardcoded end-condition effect string | A and B |
| `flags.game_finished = True` | Flag name as attribute access | A and B |

#### `game_service.py`

| Location | Violation | Fix needed for |
|----------|-----------|----------------|
| Import of `HeirState`, `StewardState` | Character-specific classes imported in service | A and B |
| `CastState(steward=StewardState(...), heir=HeirState(...))` | Character names hardcoded at session initialization | A and B |
| `gs.flags.game_finished`, `gs.flags.archive_unlocked` | Direct attribute access by scenario-specific name | A and B |
| `gs.conversation_state.steward_pressure` | Direct attribute access on character-specific counter | A and B |
| Narrator template key `"archive_discovery"` | Scenario-specific template name in code | A and B |
| `"You enter the archive."` literal string | Scenario-specific narrative text in service code | A and B |

#### `prompt_builder.py`

| Location | Violation | Fix needed for |
|----------|-----------|----------------|
| `{{steward_pressure}}` template placeholder | Character-specific variable in prompt template | A: generalize / B: fully data-driven |
| `{{may_yield}}`, `{{may_deny}}`, `{{may_deflect}}`, `{{may_hint}}` | Scenario-specific constraint names in template | A: keep, add extensibility / B: loop over dict |

---

### 2.3 API Layer (`backend/app/api/`)

#### `dto.py`

| Location | Violation | Fix needed for |
|----------|-----------|----------------|
| `FlagsDTO.archive_unlocked`, `.game_finished` | Scenario-specific flag names in API contract | A and B |
| `GameStatusDTO.steward_pressure` | Character-specific counter in API response shape | A and B |

#### `routes.py`

| Location | Violation | Fix needed for |
|----------|-----------|----------------|
| `gs.flags.archive_unlocked`, `gs.flags.game_finished` | Direct attribute access by name in route handler | A and B |
| `gs.conversation_state.steward_pressure` | Direct attribute access by name in route handler | A and B |

---

### 2.4 Tests (`tests/`)

| File | Violation | Fix needed for |
|------|-----------|----------------|
| `test_api_smoke.py` | `FLAGS_FIELDS = {"archive_unlocked", "game_finished"}`, `"steward_pressure"`, `"heir"` hardcoded as expected response keys | A and B |
| `test_constraint_builder.py` | `steward_before_unlock`, `steward_after_unlock`, `heir_default` in fixture construction | A and B |
| `test_character_responder.py` | `addressed_character="steward"`, `"heir"`, `ResponseConstraints(may_deny=True)` etc. | A and B |
| `test_prompt_builder.py` | `"steward"`, `"heir"`, `steward_pressure` in state snapshots and assertions | A and B |
| `test_validators.py` | `ConstraintRules(steward_before_unlock=..., heir_default=...)` in multiple fixtures | A and B |
| `test_game_integration.py` | `StateEffects(increase_steward_pressure=True)` repeated across test cases | A and B |

---

### 2.5 Scenario JSON Files (`scenarios/manor/`)

#### `logic.json`

| Field | Violation | Fix needed for |
|-------|-----------|----------------|
| `constraint_rules.steward_before_unlock`, `.steward_after_unlock`, `.heir_default` | Character names as fixed JSON keys | A: replace with character-ID-indexed map / B: generic condition-keyed map |
| Gate effect string `"unlock_archive"` | Used as a literal that Python code pattern-matches with `==` | A: register effect handlers / B: full data-driven op |

#### `initial_state.json`

| Field | Violation | Fix needed for |
|-------|-----------|----------------|
| `initial_flags.archive_unlocked`, `.game_finished` | Scenario-specific flag names as fixed JSON keys | A and B: replace with generic `flags: dict[str, bool]` |
| `initial_conversation_state.steward_pressure` | Character-specific counter | A and B: move to generic `counters: dict[str, int]` |
| `initial_cast_state.steward`, `.heir` | Character names as fixed JSON keys | A and B: replace with `cast: dict[character_id, CharacterState]` |

---

## 3. High-Level Engine Concepts and How Each Can Be Generated

| Concept | Current form | Generic form | How it can be generated |
|---------|-------------|--------------|------------------------|
| **Characters** | `CharacterDefinition` typed fields | Already generic; only `CastState` hardcodes names | Story brief → LLM: name, role, personality, knowledge |
| **Character portraits** | Static `.png` files on disk | Same path structure, generated on demand | `visual_description` field → text-to-image model |
| **Locations** | `LocationDefinition` typed fields | Already generic; exits hardcoded in Python | Story brief → LLM: location list; exits defined in JSON |
| **Location backgrounds** | Static `.png` files on disk | Same path structure, generated on demand | `description` + `era_feeling` → text-to-image model |
| **Flags** | Typed `FlagsState` Pydantic fields | `dict[str, bool]` from `initial_state.json` | Story brief → LLM: flag names and initial values |
| **Counters** | `steward_pressure: int` typed field | `dict[str, int]` from `initial_state.json` | Story brief → LLM: counter names and max values |
| **Character runtime state** | `StewardState`, `HeirState` typed classes | `dict[character_id, dict[str, Any]]` | Derived from character definitions + `logic.json` |
| **Claims** | `Claim` typed model — already generic | Already generic | Story brief → LLM: claim list |
| **Gates** | `Gate` typed model — mostly generic | `effect` must become a registered symbol | Story brief → LLM: gate conditions and named effect |
| **Gate effects** | `if gate.effect == "unlock_archive"` | A: registered effect dispatch / B: data-driven op | Story brief → LLM names effects; engine maps to handlers |
| **End conditions** | `EndCondition` typed model — mostly generic | Already generic | Story brief → LLM: trigger, location, flag, effect |
| **Constraint sets** | `ConstraintRules` with character-specific typed fields | A: `dict[str, ConstraintRuleSet]` / B: `dict[str, dict[str, bool]]` | Story brief → LLM: per-character constraint rules |
| **Constraint lookup logic** | `"heir"` literal in `constraint_builder.py` | Character ID looked up in a `constraint_rules` dict | Derived from character IDs in `characters.json` |
| **Pressure rules** | `PressureRules` with fixed field names | Already generic in values; field name `steward_pressure` is specific | Story brief → LLM: counter name and max value |
| **Character system prompts** | Static `.txt` files, one per character | Same; file names derived from `character.id` | Story brief + character data → LLM: character voice |
| **Style hints** | `StyleHints` in `prompt_context.json` | Already generic | Story brief → LLM: tone, vocabulary, era |
| **Narrator templates** | Static keys in `prompts/narrator.yaml` | Keys must be generic or data-driven | Story brief + locations → LLM: narrator text templates |
| **Suggestions by context** | `suggestions_by_context` in `prompt_context.json` | Already generic | Story brief → LLM: suggestion lists per context |

---

## 4. Alternative Solution Paths

### 4.1 Flags and Counters — How to Make Them Generic

#### Option A1 — Generic dicts in the Python runtime

Replace `FlagsState` typed fields and `ConversationState.steward_pressure` with:

```python
class FlagsState(BaseModel):
    flags: dict[str, bool] = {}

class ConversationState(BaseModel):
    counters: dict[str, int] = {}
    # ... rest unchanged
```

`initial_state.json` becomes:
```json
{
  "initial_flags": { "archive_unlocked": false, "game_finished": false },
  "initial_counters": { "steward_pressure": 0 }
}
```

All runtime code accesses `flags["archive_unlocked"]` instead of `flags.archive_unlocked`.

**Pros:** Minimal refactor; JSON schema stays stable; typed boundary at load time; no startup magic.  
**Cons:** Loses static type safety on flag access; API DTOs must expose dicts (breaking API change); mistyped key names fail at runtime, not at import time.

---

#### Option A2 — Dynamic Pydantic model generation at startup

A `SchemaCompiler` reads `initial_state.json` at startup and generates Pydantic models with `pydantic.create_model(...)`:

```python
FlagsState = create_model("FlagsState", **{k: (bool, v) for k, v in flags_schema.items()})
```

Attribute-style access (`flags.archive_unlocked`) works for the duration of a session.

**Pros:** Retains Pydantic field validation; attribute-style access works; IDE autocomplete works within a session context.  
**Cons:** `mypy` and static analysis cannot check generated fields; complex to implement and test; app must restart to switch scenarios; serialization of generated models requires extra care.

---

**[DECISION 2] Choose flag/counter strategy: dict (A1) or dynamic Pydantic (A2)?**

---

### 4.2 Cast State — How to Make It Generic

#### Option B1 — Dict-keyed cast state

```python
class CharacterState(BaseModel):
    available: bool = True
    extra: dict[str, Any] = {}   # e.g. {"yielded": False}

class CastState(BaseModel):
    characters: dict[str, CharacterState] = {}
```

`available_characters` iterates `cast_state.characters` instead of hardcoding steward/heir.

**Pros:** Any number of characters; no Python changes when the cast changes; easy to author in JSON.  
**Cons:** `extra` is untyped — validation of character-specific fields (e.g. `yielded`) is lost; accessing `extra["yielded"]` in service code is fragile.

---

#### Option B2 — Per-character compiled state schema

Each character definition in `characters.json` declares its own state schema:

```json
{
  "id": "steward",
  "state_schema": { "yielded": false }
}
```

At startup, a typed `CharacterState` model is generated per character using `create_model`.

**Pros:** Full Pydantic validation of character-specific state fields; less runtime key-miss risk.  
**Cons:** More complex startup; partially dynamic; `mypy` cannot check generated models; same caveats as A2 for static analysis.

---

**[DECISION 3] Choose cast state strategy: untyped dict (B1) or per-character compiled schema (B2)?**

---

### 4.3 Gate Effects — How to Make Dispatch Generic

Currently `state_updater.py` contains `if gate.effect == "unlock_archive": flags.archive_unlocked = True`.

#### Option C1 — Effect dispatch table (preferred for same-genre scope)

A fixed set of known effects is registered at startup. Each gate names one. The updater dispatches to a handler function:

```python
EFFECT_HANDLERS: dict[str, Callable[[FlagsState, CastState, ConversationState, ScenarioLogic], None]] = {
    "set_flag":            handle_set_flag,
    "set_character_state": handle_set_character_state,
    "game_finished":       handle_game_finished,
}
```

Gate effects in `logic.json` reference these registered names. New effect types require a code change.

**Pros:** Explicit; type-safe handler signatures; auditable; easy to unit-test each handler.  
**Cons:** Still requires code changes for genuinely new mechanic types; handler set must be kept in sync with allowed effect names in JSON.

---

#### Option C2 — Data-driven effect operations (required for genre-agnostic scope)

Gate effects are expressed as structured operations in `logic.json`:

```json
{
  "effect": [
    { "op": "set_flag",            "key": "archive_unlocked", "value": true },
    { "op": "set_character_state", "character": "steward", "key": "yielded", "value": true },
    { "op": "set_counter",         "key": "steward_pressure", "value": 2 }
  ]
}
```

`state_updater` interprets these as a data operation sequence, not named effect strings.

**Pros:** No code changes for new scenario effects; fully data-driven; composable operations.  
**Cons:** An operation language must be designed, validated, and documented; complex to debug; LLM generation of op sequences must be validated carefully; authoring errors in JSON cause silent failures.

---

**[DECISION 4] Choose gate effect strategy: dispatch table (C1) or data-driven ops (C2)?**

---

### 4.4 Constraint Lookup — How to Make It Generic

Currently `ConstraintBuilder` hardcodes `if game_state.addressed_character == "heir"` and accesses `rules.heir_default`.

#### Option D1 — Ordered condition list in `logic.json`

```json
"constraint_rules": [
  {
    "character_id": "steward",
    "condition": { "flag": "archive_unlocked", "value": false },
    "constraints": { "may_yield": false, "may_deny": true, "may_deflect": true, "may_hint": false }
  },
  {
    "character_id": "steward",
    "condition": { "flag": "archive_unlocked", "value": true },
    "constraints": { "may_yield": true, "may_deny": false, "may_deflect": false, "may_hint": false }
  },
  {
    "character_id": "heir",
    "condition": null,
    "constraints": { "may_yield": false, "may_deny": false, "may_deflect": false, "may_hint": true }
  }
]
```

`ConstraintBuilder` evaluates the list top-to-bottom, returning the first matching rule for the addressed character.

**Pros:** Any number of characters; any flag-based condition; no Python changes for new scenarios; natural priority ordering.  
**Cons:** A small condition expression language must be designed and validated; more verbose JSON.

---

#### Option D2 — Character-keyed map with named condition slots

```json
"constraint_rules": {
  "steward": {
    "default":               { "may_yield": false, "may_deny": true,  "may_deflect": true,  "may_hint": false },
    "when_archive_unlocked": { "may_yield": true,  "may_deny": false, "may_deflect": false, "may_hint": false }
  },
  "heir": {
    "default": { "may_yield": false, "may_deny": false, "may_deflect": false, "may_hint": true }
  }
}
```

`ConstraintBuilder` looks up `rules[character_id]` and picks the right sub-key by evaluating named conditions defined alongside each key.

**Pros:** More readable JSON; human-authorable without learning a condition language; straightforward lookup logic.  
**Cons:** Named condition slots (`when_archive_unlocked`) still require a small evaluation step; less flexible than D1 for complex multi-flag conditions.

---

**[DECISION 5] Choose constraint lookup strategy: ordered condition list (D1) or character-keyed map with named slots (D2)?**

---

## 5. Asset Generation Service

The engine currently requires these assets to exist on disk before a session can start:

```
scenarios/{id}/story.json
scenarios/{id}/characters.json
scenarios/{id}/locations.json
scenarios/{id}/logic.json
scenarios/{id}/initial_state.json
scenarios/{id}/prompt_context.json
scenarios/{id}/assets.json
assets/scenarios/{id}/portraits/{character_id}.png
assets/scenarios/{id}/backgrounds/{location_id}.png
prompts/{id}/{character_id}_system.txt
prompts/{id}/narrator.yaml
```

### 5.1 Deployment Models for Generation

#### Model 1 — Offline Authoring Tool (pre-game pipeline)

A standalone script (`tools/scenario_generator.py`) accepts a **story brief** (plain text or structured YAML) and writes a complete scenario package to disk. The game API has no knowledge of generation.

```
story_brief.txt → scenario_generator.py → scenarios/{id}/ + assets/
```

**Pros:** Clean separation; generated assets can be human-reviewed and edited before play; reproducible; game API stays simple and stateless.  
**Cons:** Requires running a separate step before first play; not immediately playable; requires developer/author access to the generation tool.

---

#### Model 2 — In-game Agentic World-Builder NPC (runtime generation during play)

A "world-builder" meta-NPC is added to the game. The player converses with this NPC to define the story world. As the conversation progresses, the NPC orchestrates asset generation and registers the scenario in real-time.

```
Player ↔ World-builder NPC ↔ AssetGenerationService → scenarios/{id}/ + assets/
```

This NPC could be:
- **Player-facing and narrative**: framed as a storyteller or oracle who "conjures" the world.
- **Administrative**: a setup wizard before the game proper starts.

**Pros:** Immersive; interactive; no separate tooling step; multi-turn conversation can refine and improve quality.  
**Cons:** Much more complex to implement; game API must support async asset generation mid-session; partial asset states during generation require safe handling; harder to test; the world-builder conversation itself must be designed and prompted carefully.

---

#### Model 3 — Hybrid: Generation API + Optional Conversational Frontend

The generation logic is implemented as a dedicated FastAPI router (`/scenario-builder/...`). It can be called:
- **Headlessly** by a script (equivalent to Model 1).
- **Through a browser UI** "create scenario" flow.
- **Via a conversational NPC facade** (making Model 2 the UI layer on top of Model 3).

**Pros:** Most flexible; reuses existing backend infrastructure; same generation logic serves admin and player-facing flows; can add rate limiting and auth to the builder endpoint separately.  
**Cons:** Most implementation work; requires a UI for player-facing mode; API security must be designed (who is allowed to trigger generation?).

---

**[DECISION 6] Choose generation deployment model: offline tool (1), in-game NPC (2), or hybrid API (3)?**

---

### 5.2 What Each Asset Requires and How It Is Generated

#### Structured JSON assets (LLM with structured output)

| Asset | Depends on | LLM task | Validated by |
|-------|-----------|----------|-------------|
| `story.json` | Story brief | Generate `scenario_id`, `title`, `premise`, `story_truth`, `ending_summary` | `Story` Pydantic model |
| `characters.json` | `story.json` | Generate character list: id, name, role, personality, knowledge, `visual_description` | `CharactersFile` |
| `locations.json` | `story.json`, `characters.json` | Generate location list: id, name, description, `background_asset`, `initially_available`, exits | `LocationsFile` |
| `logic.json` | `story.json`, `characters.json`, `locations.json` | Generate claims, gates, end conditions, pressure rules, constraint rules | `ScenarioLogic` (generalized) |
| `initial_state.json` | `characters.json`, `locations.json`, `logic.json` | Generate starting location, addressed character, initial flags, counters, cast state | `InitialState` (generalized) |
| `prompt_context.json` | `story.json`, `characters.json` | Generate style hints, story truth prompt form, suggestions by context | `PromptContext` |
| `assets.json` | `characters.json`, `locations.json` | Generate portrait/background path map | `AssetManifest` |
| `{char_id}_system.txt` | `characters.json`, `story.json` | Generate character voice and behavioural system prompt | Length and content checks |
| Narrator templates | `story.json`, `locations.json` | Generate narrator text templates keyed by generic event names | Presence check per expected key |

#### Image assets (text-to-image model)

| Asset | Input prompt source | Notes |
|-------|-------------------|-------|
| Character portrait | `visual_description` from `characters.json` | One image per character |
| Location background | `description` from `locations.json` + `style_hints.era_feeling` | One image per location |

Two image generation backends are possible:

**Approach I1 — OpenAI DALL-E**  
Uses the same API key already in use; no extra credentials or infrastructure.  
**Pros:** Simple to integrate; single dependency; consistent quality baseline.  
**Cons:** DALL-E style may not suit all narrative aesthetics; higher cost per image; no offline option.

**Approach I2 — External image service**  
Routes generation to Stable Diffusion (local via ComfyUI, or hosted via Replicate, fal.ai, etc.).  
**Pros:** More control over model choice and style; cheaper at scale; can run offline.  
**Cons:** Extra service to operate and integrate; more complex deployment; requires additional API credentials or local GPU.

---

**[DECISION 7] Choose image generation backend: DALL-E (I1) or external service (I2)?**

---

### 5.3 Generation Dependency Order

Assets must be generated in this sequence (each step may call the LLM once with a structured output schema):

```
1.  story.json              — no dependencies
2.  characters.json         — depends on: story.json
3.  locations.json          — depends on: story.json, characters.json
4.  logic.json              — depends on: story.json, characters.json, locations.json
5.  initial_state.json      — depends on: characters.json, locations.json, logic.json
6.  prompt_context.json     — depends on: story.json, characters.json
7.  assets.json             — depends on: characters.json, locations.json
8.  Character system prompts — depends on: characters.json, story.json  (one call per character)
9.  Narrator templates      — depends on: story.json, locations.json
10. Portrait images         — depends on: characters.json              (parallelizable per character)
11. Background images       — depends on: locations.json, prompt_context.json (parallelizable per location)
```

Each step must:
1. Call the LLM with a structured output schema.
2. Validate the result with the corresponding Pydantic model.
3. Write to disk (or pass in-memory to the next dependent step).
4. In offline tool mode: optionally pause for human review/edit before proceeding.

---

## 6. New Files and Concepts That Must Be Defined

| Item | Purpose | Blocked on |
|------|---------|-----------|
| `scenarios/{id}/scenario_brief.txt` | Human-written story brief — primary input to generation | — |
| Story brief format spec | Defines what a brief must contain for reliable generation | [DECISION 1] |
| Generic `FlagsState`, `CastState` in `game_state.py` | Replace typed character-name fields | [DECISION 2], [DECISION 3] |
| Generic `ConstraintRules`, `InitialState` in `scenario_models.py` | Remove character-name-keyed typed fields | [DECISION 5] |
| Generic `StateEffects` in `progress_models.py` | Remove `unlock_archive`, `increase_steward_pressure` typed fields | [DECISION 4] |
| Updated `constraint_builder.py` | No hardcoded character names; reads constraint map from scenario | [DECISION 5] |
| Updated `state_updater.py` | Effect dispatch instead of string-matching on gate effect names | [DECISION 4] |
| Updated `game_service.py` | No imports of `StewardState`/`HeirState`; generic cast initialization | [DECISION 3] |
| Updated API DTOs | Expose generic flag/counter maps instead of typed fields | [DECISION 2] |
| `tools/scenario_generator.py` or `backend/app/services/scenario_generator.py` | Orchestrates sequential LLM calls to produce a complete scenario package | [DECISION 6] |
| `tools/image_generator.py` or image generation service | Generates portrait and background images from text descriptions | [DECISION 7] |
| Condition expression language (in `logic.json`) | Expresses when a constraint rule applies; evaluated by `ConstraintBuilder` | [DECISION 4], [DECISION 5] |

---

## 7. Recommended Implementation Order (after decisions are made)

1. **Generalize domain models** — `game_state.py`, `scenario_models.py`, `progress_models.py`. Data layer first; no service changes yet.
2. **Migrate `scenarios/manor/` JSON** to the new generic schema. Verify the existing scenario still loads and all tests still pass.
3. **Update `state_updater.py` and `constraint_builder.py`** to use generic accessors and the chosen dispatch/lookup strategy.
4. **Update `game_service.py`** to remove all character-name references and hardcoded narrative strings.
5. **Update API DTOs and routes** to expose generic flag/counter maps.
6. **Update/rewrite tests** to use generic fixtures that do not reference `steward`, `heir`, `archive_unlocked`, or `steward_pressure` by name.
7. **Implement `ScenarioGenerator`** service (offline tool or API, per [DECISION 6]).
8. **Implement image generation** (per [DECISION 7]).
9. **Wire generator to agentic NPC or UI** (per [DECISION 6]).

---

## Summary of Required Decisions

| # | Decision | Options |
|---|----------|---------|
| 1 | Engine scope | A: same-genre mystery / B: genre-agnostic |
| 2 | Flag/counter representation | A1: `dict[str, bool/int]` / A2: dynamic Pydantic |
| 3 | Cast state representation | B1: `dict[str, CharacterState]` / B2: compiled per-character schema |
| 4 | Gate effect dispatch | C1: handler dispatch table / C2: data-driven op language |
| 5 | Constraint lookup | D1: ordered condition list / D2: character-keyed map with named slots |
| 6 | Asset generation deployment | 1: offline tool / 2: in-game NPC / 3: hybrid API |
| 7 | Image generation backend | I1: DALL-E / I2: external service |
