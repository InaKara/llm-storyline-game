# Phase 4 Explained — LLM Integration (AI Client, Prompts, Runners, Services)

Phase 4 builds all the pieces needed to replace the mock evaluator and mock responder with real OpenAI API calls. The pieces are not wired into the game service yet — that happens in Phase 5. Think of Phase 4 as building the engine parts; Phase 5 installs them into the car.

---

## Guided walkthrough

### 1. AI Client — `backend/app/ai/client.py`

A thin wrapper around the OpenAI Python SDK. The rest of the application never imports `openai` directly.

```python
class AIClient:
    def __init__(self, api_key, evaluator_model, responder_model):
        self._client = openai.OpenAI(api_key=api_key)
```

Two methods with different output modes:

```python
    def run_structured(self, system_prompt, user_prompt, schema, *, model=None) -> dict:
        response = self._client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "evaluator_output",
                    "schema": schema,
                    "strict": True,
                },
            },
        )
        return json.loads(response.output_text)
```

`run_structured` uses the **Responses API** with `json_schema` format. The `strict: True` flag tells OpenAI to force the model to output valid JSON matching the schema exactly. This is critical for the evaluator — we need typed data, not free text.

```python
    def run_text(self, system_prompt, user_prompt, *, model=None) -> str:
        response = self._client.responses.create(...)
        return response.output_text
```

`run_text` returns plain text — used for character dialogue where we want natural language.

**Why this API, not Chat Completions?** The Responses API is OpenAI's newer interface that natively supports structured outputs. Chat Completions can do it too (via `response_format`), but the Responses API is cleaner for this use case.

**Why wrap the SDK?** If you switch to Azure OpenAI, Anthropic, or a local model, only this file changes. Every other service calls `ai_client.run_structured()` or `ai_client.run_text()`.

---

### 2. Prompt Templates — `backend/app/prompts/`

Prompts live in text files, not Python code. This makes them:
- **Editable** without touching code
- **Versionable** in git (you can see prompt changes in diffs)
- **Inspectable** by non-developers

The directory structure:

```
backend/app/prompts/
├── evaluator/
│   ├── system.txt          # Role: "You are a game progression evaluator..."
│   ├── task.txt             # Per-turn context with {{placeholders}}
│   └── output_schema.json   # JSON Schema for structured output
├── responder/
│   ├── common_system.txt    # Shared rules for all characters
│   ├── steward_system.txt   # Mr. Hargrove's personality + constraint behaviour
│   ├── heir_system.txt      # Lady Ashworth's personality + constraint behaviour
│   └── task.txt             # Per-turn context with {{placeholders}}
└── narrator/
    ├── scene_transition.txt  # "You make your way to {{location_name}}..."
    ├── archive_discovery.txt # Static prose for the archive scene
    └── ending.txt            # Resolution narration
```

**Layered prompt composition:** The system prompt defines *who the model is* (stable across turns). The task prompt provides *per-turn context* (changes every turn). This separation keeps prompts maintainable.

The evaluator system prompt includes rules like:
- "Return ONLY structured JSON"
- "Do not invent new facts"
- "Be conservative: only match a claim if the player clearly addresses it"

The responder system prompt chains common rules + character-specific personality:
- Common: "Never reveal hidden truth unless may_yield=true"
- Steward: pressure-level behaviour (calm → tense → cornered)
- Heir: "Express doubts but never state hidden truths as known facts"

---

### 3. Prompt Loader — `backend/app/services/prompt_loader.py`

Reads template files from disk and returns them as dictionaries. Like `ScenarioLoader` from Phase 2, this isolates file I/O.

```python
class PromptLoader:
    def load_evaluator_templates(self) -> dict:
        return {
            "system": self._read("evaluator", "system.txt"),
            "task": self._read("evaluator", "task.txt"),
            "schema": self._read_json("evaluator", "output_schema.json"),
        }
```

Templates are loaded once at startup and cached in the `PromptBuilder`.

---

### 4. Prompt Builder — `backend/app/services/prompt_builder.py`

Takes loaded templates and fills in per-turn context. This is where **layered composition** happens.

#### Evaluator prompt building

```python
def build_evaluator_prompt(self, evaluator_input, claims) -> tuple[str, str]:
    claims_text = "\n".join(f"- {c.id}: {c.description}" for c in claims)
    task = self._eval["task"]
    task = task.replace("{{player_utterance}}", evaluator_input.player_utterance)
    task = task.replace("{{claims}}", claims_text)
    ...
    return system, task
```

The claims from `logic.json` are formatted into a list that the LLM can match against. Recent turns are included so the LLM has conversation context.

#### Responder prompt building

```python
def build_responder_prompt(self, responder_input, prompt_context) -> tuple[str, str]:
    if "hargrove" in char_id or char_id == "steward":
        char_system = self._resp["steward_system"]
    else:
        char_system = self._resp["heir_system"]
    common = self._resp["common_system"].replace("{{tone}}", prompt_context.style_hints.tone)
    system = f"{common}\n\n{char_system}"
```

The responder system prompt is **two parts concatenated**: common rules + character-specific rules. The task prompt includes the `ResponseConstraints` values (`may_yield`, `may_deny`, etc.) so the LLM knows what it's allowed to do.

#### Narrator text

```python
def build_narrator_text(self, template_key, context) -> str:
    text = self._narr[template_key]
    for key, value in context.items():
        text = text.replace(f"{{{{{key}}}}}", str(value))
    return text
```

Simple string substitution — narration doesn't need LLM generation.

---

### 5. Evaluator Runner — `backend/app/ai/evaluator_runner.py`

Calls the AI client with structured output and handles failure.

```python
class EvaluatorRunner:
    def run(self, system_prompt, task_prompt, output_schema) -> ProgressEvaluatorOutput:
        for attempt in range(2):
            try:
                raw = self._client.run_structured(...)
                return ProgressEvaluatorOutput(**raw)
            except Exception as exc:
                logger.warning("Evaluator attempt %d failed: %s", attempt + 1, exc)
        return self._fallback()
```

**Retry + fallback pattern:** Try once. If it fails (network error, schema mismatch, rate limit), retry once. If that also fails, return a safe no-op `ProgressEvaluatorOutput` with `intent="other"` and no effects. The game doesn't crash — the turn is just treated as a non-event.

The fallback:
```python
    @staticmethod
    def _fallback() -> ProgressEvaluatorOutput:
        return ProgressEvaluatorOutput(
            intent="other", matched_claim_ids=[], state_effects=StateEffects(),
            explanation="[Fallback — evaluator failed]",
        )
```

---

### 6. Responder Runner — `backend/app/ai/responder_runner.py`

Same retry + fallback pattern, but for plain text:

```python
class ResponderRunner:
    def run(self, system_prompt, task_prompt) -> str:
        for attempt in range(2):
            try:
                return self._client.run_text(...)
            except Exception:
                ...
        return "..."
```

The fallback is `"..."` — an ellipsis. The character says nothing rather than crashing.

---

### 7. Progress Evaluator Service — `backend/app/services/progress_evaluator.py`

The domain-level boundary between game logic and AI calls.

```python
class ProgressEvaluator:
    def evaluate(self, player_utterance, game_state, scenario_package) -> ProgressEvaluatorOutput:
        evaluator_input = ProgressEvaluatorInput(
            player_utterance=player_utterance,
            visible_scene=game_state.location,
            addressed_character=game_state.addressed_character,
            story_truth=scenario_package.story.story_truth,
            flags=game_state.flags,
            conversation_state=game_state.conversation_state,
            ...
        )
        system_prompt, task_prompt = self._builder.build_evaluator_prompt(evaluator_input, claims)
        return self._runner.run(system_prompt, task_prompt, schema)
```

**Why this layer exists:** `GameService` shouldn't know about prompts. `EvaluatorRunner` shouldn't know about `GameState`. `ProgressEvaluator` translates between the two domains.

Data flow: `GameState` → `ProgressEvaluatorInput` → `PromptBuilder` → prompt strings → `EvaluatorRunner` → `ProgressEvaluatorOutput`

---

### 8. Character Responder Service — `backend/app/services/character_responder.py`

Same pattern for the response side:

Data flow: `GameState` + `ResponseConstraints` → `CharacterResponderInput` → `PromptBuilder` → prompt strings → `ResponderRunner` → dialogue string

---

## Phase 4 Review Fixes

### Fix 1: Scenario-Generic Responder (Medium-High)

**Problem:** `PromptLoader` hardcoded two templates (`steward_system.txt`, `heir_system.txt`), and `PromptBuilder` selected between them by checking character name substrings (`"hargrove" in char_id`). Adding any new character would require code changes.

**Solution:**
- `PromptLoader.load_responder_templates()` now **scans** the `responder/` directory for any `*_system.txt` files and keys them by ID (e.g., `steward_system.txt` → key `"steward"`). Returns `{"character_systems": {"steward": "...", "heir": "..."}, ...}` instead of hardcoded fields.
- `PromptBuilder.build_responder_prompt()` now accepts an optional `CharacterDefinition` parameter and looks up by `character_id` in `state_snapshot`. If no template file exists for that character, it falls back to building a system prompt from the character's `personality` and `knowledge` fields in the scenario data. If even that isn't available, it uses a minimal "respond in character" prompt.

This means authors can add characters by simply adding a `newchar_system.txt` file, or rely purely on scenario JSON data.

### Fix 2: Player Side of Conversation in Prompts (Medium)

**Problem:** The evaluator only rendered `"speaker: dialogue"` for recent turns, dropping the player's input entirely. The responder used a dict format (`turn_0: "speaker: dialogue"`) that also omitted the player side.

**Solution:**
- Evaluator recent turns now render as: `Player: {player_input}\n  {speaker}: {dialogue}`
- Responder recent turns changed from a `dict` to a `list[dict]` with `player_input`, `speaker`, and `dialogue` keys. The prompt builder iterates this list to produce the same interleaved format.

Both the LLM evaluator and responder can now see the full dialogue transcript.

### Fix 3: All prompt_context Fields Used (Medium)

**Problem:** `PromptContext.style_hints.vocabulary`, `.era_feeling`, and `.story_truth_prompt_form` were modeled but never injected into prompts. Only `tone` was consumed.

**Solution:**
- `build_responder_prompt()` now injects `VOCABULARY GUIDANCE`, `ERA FEELING`, and `NARRATIVE CONTEXT` (from `story_truth_prompt_form`) into the system prompt alongside the existing `tone`.
- `build_evaluator_prompt()` now accepts an optional `PromptContext`. When `story_truth_prompt_form` is provided, it's used instead of the raw JSON-dumped `story_truth` — giving the LLM human-authored narrative context rather than a machine-readable structure.

### Fix 4: Service Integration Tests (Medium)

**Problem:** `ProgressEvaluator` and `CharacterResponder` services had no tests.

**Solution:** Added two test files:
- `tests/test_progress_evaluator.py` — 3 tests: runner receives correct prompts, player input appears in transcript, `story_truth_prompt_form` used when available.
- `tests/test_character_responder.py` — 5 tests: runner called with string prompts, player transcript included, vocabulary/era in system prompt, correct character template selected for steward and heir.

All tests mock the runner to avoid LLM calls while verifying the full domain boundary flow: `GameState` → `ScenarioPackage` → prompt construction → runner invocation.

```python
class CharacterResponder:
    def respond(self, game_state, evaluator_output, response_constraints,
                player_utterance, scenario_package) -> str:
        responder_input = CharacterResponderInput(
            speaker=speaker_name,
            player_utterance=player_utterance,
            intent=evaluator_output.intent,
            response_constraints=response_constraints,
            state_snapshot={...},
        )
        system_prompt, task_prompt = self._builder.build_responder_prompt(responder_input, prompt_context)
        return self._runner.run(system_prompt, task_prompt)
```

The `state_snapshot` dict includes location, steward pressure, summary, and recent turns — everything the LLM needs without exposing the full `GameState` object.

---

## Key Concepts and Terminology

### Structured Output vs Plain Text

| Method | Used for | Output | Enforcement |
|--------|----------|--------|-------------|
| `run_structured()` | Evaluator | JSON dict matching schema | `strict: True` — model forced to comply |
| `run_text()` | Responder | Natural language string | None — free text |

The evaluator *must* return typed data (which claims matched, what effects to apply). Structured output guarantees the JSON is valid. The responder returns dialogue — it needs to sound natural, so we don't constrain its format.

### Prompt Composition Layers

```
System prompt (stable per role)
├── Common rules ("never break character")
└── Character-specific rules ("you are Mr. Hargrove")

Task prompt (changes per turn)
├── Player utterance
├── Conversation context (recent turns, summary)
├── Game state (flags, pressure, location)
└── Constraints (may_yield, may_deny, etc.)
```

### Retry + Fallback

```
Attempt 1 ──→ success? ──→ return result
     ↓ fail
Attempt 2 ──→ success? ──→ return result
     ↓ fail
Return safe fallback (game continues)
```

This pattern means: the game never crashes due to an LLM failure. The worst case is a non-event turn.

---

## Tradeoffs and Alternatives

| Choice | Why this over alternatives | What we give up |
|--------|---------------------------|-----------------|
| Responses API over Chat Completions | Native structured output support, cleaner interface | Newer API, less community documentation |
| Prompts in files, not code | Editable without code changes, visible in diffs | Must deploy file changes alongside code |
| `str.replace()` for templating | Zero dependencies, obvious, debuggable | No conditionals/loops — Jinja2 would add those |
| 2 retries max | Keeps latency bounded (~2-4s per turn) | Rare transient failures still cause fallback |
| Separate evaluator/responder models | Cost optimization: gpt-4o for evaluation accuracy, gpt-4o-mini for fast dialogue | Two model configs to manage |
| Domain services between game and AI | Clean separation — game logic never sees prompts | Extra indirection layer |

---

## Recap

- **Introduced**: AI client wrapper (`client.py`), 10 prompt template files, prompt loader, prompt builder (layered composition), evaluator runner (structured output + retry + fallback), responder runner (text + retry + fallback), progress evaluator service, character responder service.
- **Phase 5 builds on**: Phase 5 wires these services into `GameService.submit_turn()`, replacing `_mock_evaluate()` and `_mock_respond()`. It also adds trace logging and movement detection.
- **Remember**: Phase 4 components are tested offline — prompt building is deterministic, runners are tested with mocked AI clients. No tests hit the real OpenAI API. The first real LLM call happens when Phase 5 wires everything together.
