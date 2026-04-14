# Phase 5 Explained: Game Logic Wiring

Phase 5 is where every component built in Phases 1–4 gets connected into a single working game. Before this phase, the evaluator could interpret player text, the responder could generate dialogue, the state updater could apply changes — but none of them talked to each other during actual gameplay. Now they do.

---

## 1. Trace Logger — `backend/app/core/trace_logger.py`

### What it does
Writes a structured JSON file after every turn, containing everything that happened: what the player said, what the evaluator returned, what state changed, what constraints were applied, and what the character said.

### Why it exists
LLM behavior is non-deterministic. When the evaluator misclassifies player input or the responder says something weird, you need to see the exact prompts and outputs. Traces are the debugging tool for AI behavior — they're to LLMs what stack traces are to code bugs.

### How it works
```
traces/
  {session_id}/
    turn_1.json    ← evaluator input/output, state before/after, constraints, dialogue
    turn_2.json
    turn_3.json
```

Each trace file contains:
- `player_input` — what the player typed
- `evaluator_output` — the structured output (intent, matched claims, state effects)
- `constraints` — what the responder was allowed to do
- `responder_output` — the dialogue the character said
- `state_before` / `state_after` — full GameState snapshots

The `read_latest_trace()` method finds the highest-numbered trace file by sorting, so you can always inspect the most recent turn.

---

## 2. Wiring the Game Service — `backend/app/services/game_service.py`

### What changed
The game service's `__init__` now accepts **optional** dependencies:
- `progress_evaluator: ProgressEvaluator | None` — real LLM evaluator
- `character_responder: CharacterResponder | None` — real LLM responder
- `prompt_builder: PromptBuilder | None` — for narrator templates
- `trace_logger: TraceLogger | None` — for turn logging

When these are `None`, the service falls back to the mock implementations from Phase 3. This means **tests that don't inject LLM services still work** — they get the same deterministic mocks.

### The full turn pipeline (submit_turn)

Here's the complete flow when a player submits text:

```
Player input arrives
       │
       ▼
┌─ Is it a movement command? ──── YES ──→ handle_movement()
│      ("go to archive")                     │
│                                            ▼
│                                    Narrator TurnResult
NO
│
▼
1. progress_evaluator.evaluate()
   GameState + player text → LLM → ProgressEvaluatorOutput
       │
       ▼
2. state_updater.apply_progress()
   Apply matched claims, update pressure, check gates
       │
       ▼
3. constraint_builder.build_constraints()
   Current state → may_yield / may_deny / may_deflect / may_hint
       │
       ▼
4. character_responder.respond()
   GameState + constraints + evaluator output → LLM → dialogue string
       │
       ▼
5. state_updater.append_turn()
   Record the turn in conversation history
       │
       ▼
6. Update summary from discovered topics
       │
       ▼
7. trace_logger.write_trace()
   Save all inputs/outputs for debugging
       │
       ▼
8. Return TurnResult to HTTP layer
```

### Why optional dependencies?
This is a pattern called "graceful degradation." The game works without an API key — it just uses mocks. This means:
- Tests never hit OpenAI (fast, free, deterministic)
- You can develop the frontend (Phase 6) without spending API credits
- If the API key becomes invalid, the game still runs (with dummy dialogue)

---

## 3. Input Classification — Movement Detection

### How it works
A simple regex pattern matches movement commands:

```python
_MOVEMENT_RE = re.compile(
    r"^(?:go\s+to|move\s+to|enter|walk\s+to|head\s+to)\s+(?:the\s+)?(.+)$",
    re.IGNORECASE,
)
```

This captures text like "go to the archive", "enter archive", "walk to The Study". The captured group is then resolved against location IDs and names using `_resolve_location()`.

**Crucially:** The movement is only executed if the resolved location is in `available_exits`. If you say "go to the archive" but the archive is locked, the text falls through to the evaluator/responder pipeline and gets treated as normal dialogue. This means the evaluator can interpret "go to the archive" as the player expressing intent, and the character can respond appropriately ("The archive is locked, I'm afraid").

### Why not use the LLM for movement detection?
Movement detection is a solved problem with simple patterns. Using the LLM would add latency, cost, and non-determinism for something that's inherently deterministic. The spec explicitly calls for this approach.

---

## 4. Narrator Handling

### Three narrator scenarios

1. **Session creation** — Uses the scenario's premise + starting location description.

2. **Scene transition** — When the player moves, the narrator describes the new location using the `scene_transition.txt` template: `"You make your way to {location_name}. {location_description}"`

3. **Game ending** — When the player enters the archive and the game finishes, the narrator uses two templates combined:
   - `archive_discovery.txt` — dramatic prose about finding the testament
   - `ending.txt` — resolution narration about the truth being uncovered

### Why templates, not LLM?
Narrator text is pre-authored, not generated. The narrator doesn't improvise — it delivers authored story beats at the right moments. This keeps key plot moments consistent and avoids the LLM accidentally spoiling the mystery or generating inconsistent text.

---

## 5. Service Wiring in main.py

### The conditional import pattern

```python
if settings.openai_api_key:
    from backend.app.ai.client import AIClient
    # ... create all LLM services ...
    progress_evaluator = ProgressEvaluator(prompt_builder, evaluator_runner)
    character_responder = CharacterResponder(prompt_builder, responder_runner)
```

The LLM services are only created when an API key exists. If not, `progress_evaluator` and `character_responder` remain `None`, and the game service uses mocks.

The trace logger is created unconditionally when `trace_output_path` is configured (it defaults to `traces/`).

---

## 6. Trace Endpoint — `GET /api/sessions/{id}/traces/latest`

A new HTTP endpoint that returns the latest trace for a session. This is useful for:
- Debugging during development (see exactly what the LLM received and returned)
- Inspecting evaluator behavior (did it match the right claims?)
- Verifying constraint enforcement (was the responder told `may_yield: false`?)

The endpoint delegates to `game_service.get_latest_trace()` which delegates to `trace_logger.read_latest_trace()`.

---

## 7. Phase 5 Tests — `tests/test_game_integration.py`

10 integration tests that exercise the complete turn pipeline with mocked AI services:

| Test | What it verifies |
|------|-----------------|
| `test_create_session_returns_narrator_intro` | Session creation returns narrator speaker with study location |
| `test_submit_turn_returns_character_dialogue` | Turn uses mock responder, returns character dialogue |
| `test_submit_turn_calls_evaluator` | Evaluator is called with the player's utterance |
| `test_full_accusation_unlocks_archive` | All 3 claims matched → archive_unlocked = true |
| `test_movement_after_unlock` | handle_movement to archive → game_finished = true |
| `test_movement_detection_in_submit_turn` | "Go to the archive" text detected as movement, evaluator NOT called |
| `test_movement_text_ignored_when_exit_not_available` | "Go to the archive" when locked → falls through to evaluator |
| `test_trace_written_after_turn` | Trace file written with player_input, evaluator_output, state diffs |
| `test_game_finished_narrator` | Game ending uses narrator with testament in dialogue |
| `test_reset_restores_initial_state` | After progress, reset returns to zero pressure and locked archive |

**Key approach:** These tests inject `MagicMock` evaluator and responder into the `GameService` constructor. The mocks return predetermined outputs, making the tests deterministic, fast, and free (no API calls). The `tmp_path` fixture provides a temporary directory for trace files.

---

## Summary

Phase 5 is the "glue phase." No new concepts are introduced — instead, existing components are connected. The result is a fully playable game accessible via HTTP. You can:

1. `POST /api/sessions` → start a game, get narrator intro
2. `POST /api/sessions/{id}/turns` → submit dialogue, get character responses
3. Observe state changes via `GET /api/sessions/{id}/state`
4. Type "go to the archive" after unlocking → get narrator ending
5. Inspect LLM behavior via `GET /api/sessions/{id}/traces/latest`

The entire pipeline works end-to-end: player input → evaluator → state update → constraint derivation → responder → trace → response.

---

## Phase 5 Review Fixes

### Fix 1: Numeric Trace File Sorting (High)

**Problem:** `read_latest_trace()` sorted files lexicographically. `turn_9.json` sorted after `turn_10.json` because `"9" > "1"` in string comparison. After 10+ turns, "latest" returned the wrong trace.

**Solution:** Replaced `sorted()` with `max()` using a key function that extracts the numeric turn index via regex: `re.compile(r"turn_(\d+)\.json$")`. Now `turn_10` correctly resolves as newer than `turn_9`.

### Fix 2: Movement Turns Now Traced (Medium-High)

**Problem:** The movement path in `handle_movement()` updated state, incremented the turn, and returned — but never called the trace logger. Archive entry and game ending were invisible to the trace system.

**Solution:** Added `_write_movement_trace()` method. Movement traces include `type: "movement"`, `target_location`, `narrator_dialogue`, and `state_before`/`state_after`. Called at the end of `handle_movement()`.

### Fix 3: Narrator Templates Decoupled from API Key (Medium)

**Problem:** `PromptBuilder` was only created inside the `if settings.openai_api_key:` block in `main.py`. Without an API key, narrator templates weren't loaded — movement and ending text fell back to thin hardcoded strings instead of the authored templates.

**Solution:** Moved `PromptLoader` and `PromptBuilder` creation *before* the API key conditional. Narrator text is authored content, not an AI feature — it should always be available regardless of whether LLM services are configured.

### Fix 4: Trace Test Coverage (Low-Medium)

**Problem:** Only one test checked trace existence after a normal turn. No tests covered double-digit ordering, movement traces, or the HTTP trace endpoint.

**Solution:** Added 4 new tests:
- `test_trace_double_digit_ordering` — submits 11 turns, verifies `turn_index == 11` (not 9)
- `test_movement_trace_written` — unlocks archive, moves, verifies movement trace with `type` and `target_location`
- `test_latest_trace_after_turn` — HTTP test: submit turn, GET `/traces/latest`, verify 200
- `test_latest_trace_404_no_traces` — HTTP test: create session without turns, verify 404
