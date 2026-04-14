# Phase 2 — Domain Models + Scenario Loading

Phase 2 introduces the data layer: authored JSON files that define the manor scenario, typed Python models that represent them, a loader that reads files into those models, and cross-file validation that catches consistency errors at startup. After this phase, the runtime knows what the game world looks like — but doesn't yet run sessions or call an LLM.

---

## Guided Walkthrough

### 1. Scenario JSON Files — `scenarios/manor/`

Seven JSON files define everything about "The Missing Testament" scenario:

| File | Purpose |
|------|---------|
| `story.json` | Narrative metadata: title, premise, hidden truth, ending |
| `characters.json` | Cast: steward and heir, with personality and knowledge |
| `locations.json` | Settings: study (available) and archive (locked) |
| `initial_state.json` | Starting game state: location, flags, conversation |
| `logic.json` | Progression: claims, gates, end conditions, constraint rules |
| `assets.json` | Maps character/location IDs to image paths |
| `prompt_context.json` | LLM prompt support: tone, vocabulary, suggestions |

Example — `story.json`:
```json
{
  "scenario_id": "manor",
  "title": "The Missing Testament",
  "premise": "You arrive at a manor where an important testament has gone missing...",
  "story_truth": {
    "hidden_item": "testament",
    "current_holder": "steward",
    "motive": "preserve control over the estate",
    "authority_transfers_to": "heir"
  },
  "ending_summary": "The steward yields under pressure..."
}
```

Why separate files: each file has one job. You can change character personalities without touching progression logic, or add new claims without modifying the story text. The runtime code doesn't care which specific scenario is loaded — it works with the typed models.

### 2. Scenario Domain Models — `backend/app/domain/scenario_models.py`

Each JSON file has a corresponding Pydantic model. When JSON is loaded, it's parsed into these models — if the JSON doesn't match the schema, Pydantic raises `ValidationError` immediately.

```python
class StoryTruth(BaseModel):
    """The hidden truth that drives the narrative."""
    hidden_item: str
    current_holder: str
    motive: str
    authority_transfers_to: str

class Story(BaseModel):
    """Top-level narrative metadata for a scenario."""
    scenario_id: str
    title: str
    premise: str
    story_truth: StoryTruth
    ending_summary: str
```

The key pattern: nested models. `Story` contains a `StoryTruth` — Pydantic validates the entire tree recursively. If `story_truth` is missing or has a wrong type, you get a clear error at construction time, not a `KeyError` deep in game logic later.

The `ScenarioPackage` model aggregates everything:
```python
class ScenarioPackage(BaseModel):
    story: Story
    characters: CharactersFile
    locations: LocationsFile
    initial_state: InitialState
    logic: ScenarioLogic
    assets: AssetManifest
    prompt_context: PromptContext
```

This is the single object that the rest of the application passes around — no raw dicts, no untyped JSON blobs. Note that `initial_state` is included: the package owns all authored data, including starting conditions. Phase 3 reads `initial_state` to create a new `GameState` without re-opening any JSON files.

### 3. GameState Domain Model — `backend/app/domain/game_state.py`

`GameState` represents mutable runtime state for a live session. It's separate from scenario models because scenarios are authored once and shared, while game state changes every turn.

```python
class GameState(BaseModel):
    location: str
    addressed_character: str
    flags: FlagsState = FlagsState()
    story_truth: StoryTruth
    conversation_state: ConversationState = ConversationState()
    cast_state: CastState = CastState()
```

Two derived properties compute values from current state instead of storing them separately:

```python
@property
def available_characters(self) -> list[str]:
    # NOTE: Currently checks only availability flags, not location.
    # Both characters share one room in the current scenario.
    chars: list[str] = []
    if self.cast_state.steward.available:
        chars.append("steward")
    if self.cast_state.heir.available:
        chars.append("heir")
    return chars
```

This is sufficient for the current scenario (both characters are always in the study), but when characters can be in different locations, this property must also filter by `self.location`.

@property
def available_exits(self) -> list[str]:
    exits: list[str] = []
    if self.location == "study" and self.flags.archive_unlocked:
        exits.append("archive")
    return exits
```

Why properties instead of stored fields: these values can be computed from existing state. Storing them separately would create a risk of inconsistency — for example, `available_exits` could say `["archive"]` while `flags.archive_unlocked` is still `False`. Derived properties make this impossible.

### 4. Scenario Loader — `backend/app/services/scenario_loader.py`

A single class isolates all file I/O. The rest of the application never touches the filesystem for scenario data — it receives typed `ScenarioPackage` objects.

```python
class ScenarioLoader:
    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path

    def load_scenario_package(self, scenario_id: str) -> ScenarioPackage:
        folder = self._base_path / scenario_id
        if not folder.is_dir():
            raise FileNotFoundError(f"Scenario folder not found: {folder}")

        return ScenarioPackage(
            story=Story(**self._load_json(folder / "story.json")),
            characters=CharactersFile(**self._load_json(folder / "characters.json")),
            # ... one line per file
        )

    @staticmethod
    def _load_json(path: Path) -> dict:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
```

The `**self._load_json(...)` pattern: `_load_json` returns a plain Python dict. The `**` operator unpacks it into keyword arguments for the Pydantic model constructor — same pattern used in Phase 1 with `**MOCK_SESSION_DATA`. Pydantic validates every field during construction.

Why a dedicated loader: if the file format changes (e.g., YAML later), only this file changes. Services just consume typed models.

### 5. Scenario Validators — `backend/app/core/validators.py`

Pydantic validates each file's shape, but can't check cross-file references. The validator catches things like: a gate references a claim ID that doesn't exist, or an asset references a character that isn't in `characters.json`. It also verifies that `initial_state.json` references valid locations and characters, and that the embedded asset filenames in characters/locations agree with the asset manifest.

```python
def validate_scenario_package(package: ScenarioPackage) -> list[str]:
    errors: list[str] = []

    claim_ids = {c.id for c in package.logic.claims}
    character_ids = {c.id for c in package.characters.characters}
    location_ids = {loc.id for loc in package.locations.locations}

    for gate in package.logic.gates:
        for cid in gate.required_claim_ids:
            if cid not in claim_ids:
                errors.append(f"Gate '{gate.id}' references unknown claim '{cid}'")
    # ... more checks
    return errors
```

Why return a list instead of raising an exception: returning all errors at once gives a better developer experience. If a scenario has 3 broken references, you see all 3 immediately instead of fixing them one at a time.

### 6. Debug Endpoint — `backend/app/api/routes.py`

A new `GET /api/debug/scenario/{scenario_id}` endpoint loads and returns the full scenario as JSON, including any validation errors:

```python
@router.get("/debug/scenario/{scenario_id}")
async def debug_scenario(scenario_id: str) -> dict:
    loader = ScenarioLoader(base_path=get_settings().scenario_root_path)
    package = loader.load_scenario_package(scenario_id)
    errors = validate_scenario_package(package)
    return {
        "scenario": package.model_dump(),
        "validation_errors": errors,
    }
```

The loader uses `get_settings().scenario_root_path` from the centralised config (not a hardcoded path), so the debug endpoint respects any config override.

### 7. Tests

Four test files cover Phase 2:

**`tests/test_scenario_models.py`** — Validates Pydantic catches bad data:
- Valid models construct without error
- Missing required fields raise `ValidationError`

**`tests/test_scenario_loader.py`** — Integration tests against real manor JSON files:
- `load_scenario_package("manor")` returns expected counts (2 characters, 2 locations, 3 claims)
- Non-existent scenario raises `FileNotFoundError`
- Story truth and prompt context populate correctly

**`tests/test_validators.py`** — Cross-file validation:
- Valid manor package → empty error list
- Gate referencing non-existent claim → error
- No gates defined → error
- Asset referencing unknown character → error
- No initially available location → error

**`tests/test_game_state.py`** — GameState derived properties:
- Default flags are `False`
- Both characters available by default
- Archive exit appears only when `archive_unlocked` is `True`
- Archive exit doesn't appear when already in the archive

---

## Key Concepts and Terminology

### Authored vs Runtime Data

| | Authored (Scenario) | Runtime (GameState) |
|---|---|---|
| When created | By a human, before the game runs | By the system, when a session starts |
| Mutability | Immutable — never changes during play | Mutable — changes every turn |
| Sharing | One scenario shared by all sessions | One GameState per session |
| Example | "The steward's name is Mr. Hargrove" | "The player is currently talking to the steward" |

### Nested Model Validation

Pydantic validates recursively. When you write:
```python
Story(scenario_id="manor", title="Test", premise="Test",
      story_truth={"hidden_item": "testament", "current_holder": "steward", ...},
      ending_summary="End")
```
Pydantic automatically converts the `story_truth` dict into a `StoryTruth` instance and validates all its fields. If `hidden_item` were missing, the error message would say `story_truth -> hidden_item: field required`.

### Derived Properties

A `@property` on a Pydantic model behaves like a read-only attribute but computes its value on access. It doesn't appear in `.model_dump()` output (only stored fields do), which is correct — derived values shouldn't be serialized because they'd become stale.

---

## Tradeoffs and Alternatives

| Choice | Why this over alternatives | What we give up |
|--------|---------------------------|-----------------|
| Separate JSON files per concern | Each file has one job; can edit story without touching logic | More files to manage; must cross-reference IDs manually |
| Pydantic for domain models | Type validation on construction; clear errors; IDE autocomplete | Slightly more boilerplate than plain dicts |
| GameState separate from Scenario | Many sessions can share one scenario; runtime state is independent | Two model hierarchies to maintain |
| Derived properties for exits/characters | No state duplication; impossible to be inconsistent | Recomputed on every access (negligible cost); character availability doesn't yet consider location |
| Validator returns error list | Shows all problems at once | Caller must check the list (not automatic exception) |
| Loader class with explicit methods | File I/O isolated; easy to swap format later | One more abstraction layer |
| Debug endpoint in routes.py | Inspect loaded data through the API during development | Must be removed or guarded before production |

---

## Recap

- **Introduced**: 7 scenario JSON files, 15+ Pydantic domain models (scenario + game state), a file loader, cross-file validation, and a debug endpoint. The runtime now has typed knowledge of the game world.
- **Future phases build on**: Phase 3 uses `GameState` + `ScenarioPackage` to create live sessions with state management. Phase 4 uses `PromptContext` and `ConstraintRules` to compose LLM prompts.
- **Remember**: Scenario models are immutable authored data. GameState is mutable runtime data. The loader is the only code that touches the filesystem for scenarios. Validators catch what Pydantic can't (cross-file references).
