# Adventure Game Prototype Spec and Implementation Handoff

## Purpose of this document

This document is intended to be complete enough that another LLM, engineer, or future implementation pass could start building the prototype **without needing the original discussion**.

It captures:
- product intent
- game design decisions
- software architecture decisions
- tech stack decisions
- deferred topics
- known prototype limitations
- later-stage evolution paths
- current immediate next decisions

---

## Working mode and decision style

Two hats are used depending on topic:
- **Creative gameplay co-designer** when discussing game design and mechanics
- **Technical architect** when discussing software architecture and implementation

The user is the final decision maker. Ideas remain flexible until explicitly accepted.

Response style preference for this project:
- concise
- precise
- discussion-style
- no drifting into unrelated directions

---

## Product vision

The product is a **minimal adventure game prototype** with an **LLM at its core**, but the LLM is **not** allowed to run the game freely.

The prototype uses a **fixed authored dramatic backbone**. The LLM is used to:
- interpret player free-text input
- realize in-character responses naturally
- operate within bounded story and gameplay constraints

The LLM should **not** invent the true story structure during runtime.
The true story structure is authored and fixed for the prototype.

### Design philosophy
The prototype should be:
- **more authored than generative**
- **schema-bound**
- **minimal in scope**
- **extendable later**

The goal is not to build a full adventure game yet. The goal is to test whether a bounded LLM-driven adventure interaction can feel:
- coherent
- controllable
- interesting
- structurally reliable

---

## Prototype scope

Chosen minimum scope:
- **2 characters**
- **2 settings**
- **1 gate**
- **1 key reveal**
- **1 ending**

The prototype should feel like a very small playable story puzzle, not a full game.

---

## Story design

### Selected story container
**Manor storyline**

### Premise
The player arrives at a manor where an important testament is supposedly missing.

### Characters
- **Steward**
- **Heir**

### Settings
- **Study**
- **Archive room**

### Core hidden truth
The steward already found the testament, read it, realized it transfers authority to the heir immediately, and hid it in order to preserve his own control over the estate.

### Heir knowledge
The heir does not know the truth as a fact, but suspects the steward is deliberately delaying matters rather than genuinely failing to find the document.

### Ending
The player successfully confronts the steward, the steward yields, the archive becomes reachable, the player enters the archive, the narrator describes the testament discovery, and the matter is resolved.

---

## Gate and progression design

### Chosen gate model
**Social pressure unlock**

The archive does **not** open because of a physical clue puzzle.
It opens because the player reaches the correct interpretation and confronts the steward successfully.

### Successful accusation rule
A successful accusation is **semantic**, not a single exact sentence.

To succeed, the player's accusation must clearly communicate, in substance, that:
- the steward already found the testament
- the steward is deliberately hiding or withholding it
- the reason is that the testament transfers authority to the heir and ends the steward's control

Examples of successful accusation content:
- the steward found the testament and hid it
- the testament is not missing; the steward is keeping it from the heir
- the steward is withholding it because it gives power to the heir

Examples of insufficient accusation content:
- the steward is nervous
- the steward knows more than he says
- the steward does not want the heir to read it

### Progression design choice
The gameplay rule is intentionally simple, but the **unlock decision is isolated behind a dedicated evaluator component**.

This means:
- current prototype behavior stays simple
- progression logic is not scattered through prompts or UI code
- later richer progression can replace the evaluator without rewriting the full game

---

## Location model and character addressing

### Location model for stage 1

Game state tracks one explicit `current_location` and one explicit `addressed_character`.

- Starting location: **study**
- Both steward and heir are initially present in the study
- The archive room is **not reachable** until `archive_unlocked = true`
- After unlock, the archive appears as an available exit / suggested prompt

Stage-1 state values:
- `current_location` = `study` | `archive`
- `addressed_character` = `steward` | `heir` | `narrator`
- `available_characters` = derived from current location and game state
- `available_exits` = derived from current location and game state

### Character addressing

The player can switch the addressed character in two ways:
- **UI-driven**: click/tap a character portrait or name
- **Free text**: e.g. "ask the heir…", "tell the steward…"

The backend resolves one `addressed_character` per turn.

### Movement

Movement is primarily **UI-driven** (button / suggested prompt), with free-text support as secondary (e.g. "go to archive").

Only after `archive_unlocked = true` does "Go to the archive" appear as a suggested prompt or clickable option.

### Why this model

- Simplest implementation
- Avoids roaming NPC logic
- Keeps evaluator and responder clean
- Later, character locations can be separated without changing the core model

---

## Post-unlock flow and ending sequence

The game does **not** auto-finish immediately on successful accusation.

### Detailed post-unlock sequence

1. Player makes a successful accusation → evaluator returns unlock
2. `archive_unlocked` is set to `true`
3. Steward gives a short yielding response (via responder with `may_yield = true`)
4. Archive becomes reachable as an exit
5. Player must explicitly move to the archive
6. On entering the archive, **narrator** describes the discovery of the testament
7. `game_finished` is set to `true`
8. Game ends

### Why not auto-finish

- Cleaner dramatic sequence
- Preserves the second location as meaningful
- Keeps ending logic simple and explicit

---

## Narrator

### Narrator role

A third non-character speaker exists: the **narrator**.

The narrator is **not** a full free character. It produces system-authored prose for specific events.

### Narrator is used only for

- Scene transitions (e.g. moving to the archive)
- Archive opening description
- Testament discovery
- Ending text
- Initial scene-setting text when a session starts

### Speaker type

All turn outputs carry a `speaker_type`:
- `character` — steward or heir, generated by the LLM responder
- `narrator` — system text, template-driven

### Stage-1 implementation

- Narrator text is produced by backend from **templates**, not by an LLM call
- A tiny narrator template set is sufficient
- Responder role remains for steward/heir only
- Later, narrator could be upgraded to a separate LLM role if needed

### Why template-driven

- Cheapest and safest
- Avoids a third LLM role in stage 1
- Easy to expand later

---

## Interaction model and UI design

### Chosen interaction model
The prototype will **not** use fixed-choice-only dialogue.

It will use:
- a **text input field** as the main interaction method
- placeholder guidance like: **"Ask, inspect, accuse, or tell…"**
- **3 small context-sensitive example prompts** under the input

### Internal interpretation model
Player free text is **not** treated as unconstrained simulation.

Internally, the system should:
- interpret the player's utterance
- map it into a bounded interaction model
- evaluate whether it affects progression
- generate a natural in-character response within allowed outcomes

### UI tone
The UI should preserve the feeling of free interaction while still guiding the player toward supported forms of input.

---

## Character visual representation

### Chosen stage-1 approach
Each character has:
- **1 bust portrait only**

### Explicitly rejected for v1
- free-form emotional portrait generation
- multiple generated facial variants
- dependence on facial consistency across many images

### Emotional expression strategy
Emotion in stage 1 should be conveyed mainly through:
- dialogue wording
- tone
- scene framing and writing

### Visual reference rationale
This choice is aligned with the inspiration from older static-portrait dialogue presentation styles: strong static portrait language instead of dynamic facial performance.

---

## Runtime/gameplay control philosophy

The system should hard-bound:
- the underlying story truth
- the gate condition
- the allowed progression outcomes
- the ending condition

The system should keep flexible:
- dialogue wording
- phrasing
- tone
- conversational path
- incidental flavor

The LLM should **not** become the game engine.
It should act as a bounded interpretation and realization layer.

---

## Chosen progression architecture

### Core runtime pattern
The runtime uses a small explicit progression structure with an **isolated evaluator**.

The prototype currently uses a simple unlock model, but it is architected so that progression interpretation is centralized and replaceable.

### Important distinction
The current prototype does **not** use a rich semantic progression system yet.
It uses a simple gameplay rule, but implemented cleanly.

### Why this was chosen
This preserves:
- prototype simplicity
- story reliability
- ability to extend later toward richer semantic progression

---

## Runtime architecture

### Current runtime style
A **thin main loop / coordinator** connects minimal runtime components.

This is **not** yet a rich orchestration layer.

### Exact minimal runtime components

#### 1. GameState
Single source of truth for runtime state.

Contains at least:
- current location
- addressed character
- archive unlocked state
- game finished state
- world truth
- short conversation memory / discovered facts
- recent raw turns
- steward pressure level
- available characters (derived)
- available exits (derived)

#### 2. InputHandler
Receives raw player text from the UI and forwards it into the runtime.

No story logic should live here.

#### 3. ProgressEvaluator
Dedicated isolated component that decides whether the player's latest input affects progression.

Responsibilities:
- interpret the player's intent
- detect whether the input is an accusation or other interaction type
- decide whether the accusation semantically matches the hidden truth strongly enough
- return structured progression output

This is the only place in v1 that decides unlock eligibility.

#### 4. StateUpdater
Applies evaluator results to GameState.

Responsibilities include:
- setting `archive_unlocked = true` when the unlock condition is met
- setting `game_finished = true` when the testament is found
- recording short memory updates if needed

#### 5. CharacterResponder
Generates the actual in-character response.

Responsibilities:
- produce steward or heir dialogue
- obey current game state and evaluator result
- avoid inventing new world truth
- avoid independently deciding progression

#### 6. SceneRenderer
Builds what the player sees.

Responsibilities:
- display current background
- display the current character portrait
- show response text
- show the text input field
- show 3 example prompts depending on context/state

#### 7. MainLoop / Coordinator
Thin connector among all components.

Flow:
1. player types input (or clicks movement/addressee)
2. InputHandler forwards it
3. ProgressEvaluator returns structured result
4. StateUpdater updates GameState
5. ConstraintBuilder derives response constraints
6. CharacterResponder generates reply (or narrator template is selected for system events)
7. SceneRenderer updates the UI

---

## Why evaluator isolation was chosen

The game uses a simple unlock mechanic, but the unlock decision should be isolated behind a dedicated evaluator component.

### Meaning
The unlock condition should **not** be spread across:
- the UI
- the steward prompt
- the input handler
- ad-hoc response logic

Instead, one dedicated place evaluates:
- what the player's input means for progression
- whether it unlocks the archive

### Important distinction
This does **not** change current game behavior.
It changes the **software structure** so the prototype is cleaner and later evolution is easier.

---

## Stage-1 software architecture choices

### Overall application shape
- **Web frontend + backend app**
- The frontend handles presentation and input
- The backend owns runtime game logic, state, and LLM calls

### Frontend style
- **SPA-style interaction model**, implemented lightly
- Chosen implementation direction for stage 1: **very light frontend / plain JavaScript**
- A later migration to React + Vite remains feasible because the frontend is intentionally kept thin

### Backend style
- **Minimal Python API backend**
- Chosen concrete framework: **FastAPI**

### State ownership
- **Backend-authoritative game state**
- **Frontend holds only ephemeral view state**

#### Backend authoritative state includes game truth such as:
- current story instance
- current location
- archive unlocked state
- game finished state
- conversation summary / discovered topics
- world truth
- character progression state

#### Frontend view state includes only presentation/interactivity concerns such as:
- current input text
- loading state
- temporary UI selections/highlights
- currently visible rendered response data
- local UI animation/presentation behavior

### Persistence choice for stage 1
- **No database**
- **No persistence of game sessions across restarts**
- Runtime story state is kept **in memory only**

### Session model
- **In-memory session map keyed by session ID**

### Frontend-backend communication
- **Plain HTTP per turn**
- Two LLM calls per turn (evaluator + responder) means ~2–4s latency
- Frontend shows a **single unified loading state**: input disabled, spinner / “Thinking…” text
- No split-phase loading in stage 1; one indicator is sufficient

### LLM role layout
- **Two-role layout**
  - **Evaluator** role: interprets player input and progression impact
  - **Responder** role: generates the in-character reply

### AI integration boundary
- **Dedicated internal AI service layer inside the backend**
- Backend game/runtime services should not scatter model invocation details everywhere

### Prompt organization
- **Prompts in external template files**

### Observability/debugging
- **Structured debug traces**
- Also chosen later: traces should be written as **structured files per session/turn**

### Asset/storage direction
- **Very light hybrid approach**
- Manual assets by default in stage 1
- Optional generation path kept open
- Generated artifacts/assets may be saved as files where useful

### Asset serving strategy
- **FastAPI serves static assets** via a mounted `/assets` route
- Backend responses include full asset URLs (e.g. `/assets/scenarios/manor/portraits/steward.png`)
- `assets.json` maps character/location IDs to relative asset paths; backend resolves them into URLs for frontend view models
- Frontend simply renders URLs received from backend; no frontend-side asset path guessing
- During development, Vite proxies API and asset requests to the FastAPI backend

### CORS configuration
- **FastAPI CORS middleware** is added for development
- Allow the Vite dev origin explicitly (e.g. `http://localhost:5173`)
- Keep the allowed origin narrow, not wildcard, even in prototype

### Session cleanup
- Each session stores a `last_accessed_at` timestamp
- Lightweight cleanup: lazy cleanup on new requests, or simple background interval
- Sessions expire after **30–60 minutes** of inactivity
- Optional: cap max sessions to a small number (e.g. 100)
- This is sufficient for prototype safety

### Backend module layout
- **Layered feature layout**

Suggested structure:

```text
app/
  main.py

  api/
    routes.py
    dto.py

  core/
    config.py
    session_store.py
    trace_logger.py

  domain/
    game_state.py
    story_models.py
    progress_models.py

  services/
    game_service.py
    progress_evaluator.py
    character_responder.py
    state_updater.py
    constraint_builder.py
    prompt_loader.py

  ai/
    client.py
    evaluator_runner.py
    responder_runner.py

  prompts/
    evaluator/
      system.txt
      task.txt
    responder/
      steward_system.txt
      heir_system.txt
      task.txt
```

### API shape
- **Clean game/debug split**

Chosen direction:
- `POST /sessions`
- `POST /sessions/{session_id}/turns`
- `POST /sessions/{session_id}/reset`
- `GET /sessions/{session_id}/state`
- `GET /sessions/{session_id}/traces/latest`

---

## Stage-1 tech stack choices

### Backend
- **FastAPI**

### Frontend
- **Plain JavaScript + Vite**

### OpenAI integration
- **Responses API** (explicitly chosen over Chat Completions API)
- Reason: structured output support for evaluator, newer intended API shape
- Wrapped behind `AIClient` so migration is cheap if needed later
- This is a deliberate choice and should not be confused with Chat Completions

### Output control strategy
- **Structured outputs for evaluator**
- **Natural text outputs for responder**

### Image generation direction
- **OpenAI image generation API**

### Serialization / runtime artifact format
- **JSON**

---

## Scenario packaging decisions

### Scenario packaging model
**Scenario package folder**

The runtime should load a **scenario package**, not manor-specific hardcoded values.

### Chosen package style
**Balanced package** with separate logic file.

### Locked stage-1 scenario package contents
- `story.json`
- `characters.json`
- `locations.json`
- `initial_state.json`
- `logic.json`
- `assets.json`
- `prompt_context.json`

### Logic placement decision
Gameplay logic/progression logic should live in:
- **separate `logic.json`**

This keeps narrative description distinct from runtime-facing progression logic.

### Scenario file authority boundary: story.json vs prompt_context.json

- `story.json` = **canonical narrative data** and source of truth
- `prompt_context.json` = **prompt-only helper material**, never authoritative

Rule: no new truths may exist in `prompt_context.json`. It may only contain:
- restated truths in prompt-friendly form
- vocabulary/style hints
- suggested prompt examples per context
- phrasing guidance
- compressed role-facing context

`story.json` is the single source of narrative truth. `prompt_context.json` is derived/supportive.

---

## Remaining big-decision bundle that was locked

### Session initialization flow
**Prepared session flow**

Meaning:
- load scenario package
- normalize/derive runtime data as needed
- create initial GameState
- load prompt templates
- compile initial prompt context
- session becomes ready

### Prompt composition strategy
**Layered prompt composition**

Prompt shape should conceptually be built from layers such as:
- base system template
- role template
- scenario context
- turn context
- runtime constraints

### Model strategy
**Same model now, separate role configs**

Meaning:
- evaluator and responder can use the same model initially
- but model config should already be separated per role to allow divergence later

### Startup validation
**Lightweight startup validation**

At session creation, validate:
- scenario package structure
- required files
- required references between files
- basic consistency of package contents

### Trace output destination
**Structured trace files per session/turn**

### Asset generation usage in stage 1
**Optional generation path, manual assets default**

---

## LLM failure handling

### Policy

Two LLM calls per turn means two points of failure. A tiny fallback policy is used.

### Evaluator failure handling

- Retry **once** on malformed structured output or API error
- If still fails, return a **safe fallback** evaluator result:
  - `intent = other`
  - no state effects
  - target from prior focus or none
  - empty `matched_claim_ids`

### Responder failure handling

- Retry **once** on API/timeout failure
- If still fails, return a **generic safe line** per character:
  - steward: *"I have nothing further to add."*
  - heir: *"I am not sure what to say to that."*

### Narrator

Narrator text never depends on LLM in stage 1, so no failure path needed.

### Logging

All LLM failures (including retries) are written into the **trace log** for that session/turn.

---

## Chosen schema direction

### Selected schema family
**Option 2: domain-shaped schema**

This is the current implementation direction because it balances:
- prototype simplicity
- conceptual clarity
- future extendability

### Selected schema family shape

#### GameState
- `location: { id }`
- `addressed_character: { id }`
- `flags: { archive_unlocked, game_finished }`
- `story_truth: { hidden_item, current_holder, motive, authority_transfers_to }`
- `conversation_state: { last_speaker, steward_pressure, discovered_topics, summary, recent_turns }`
- `cast_state: { steward: { available, yielded }, heir: { available } }`
- `available_characters: derived`
- `available_exits: derived`

#### ProgressEvaluatorInput
- `player_utterance`
- `visible_scene`
- `addressed_character`
- `conversation_summary`
- `story_truth`
- `flags`
- `conversation_state`

#### ProgressEvaluatorOutput
- `intent`
- `target`
- `matched_claim_ids: string[]`
- `matched_gate_condition_ids: string[]`
- `state_effects: { unlock_archive, increase_steward_pressure, mark_topic_discovered }`
- `explanation`

The evaluator does **not** use manor-specific semantic fields. Instead, `logic.json` defines the scenario's important claims and which claims are required for unlock. The evaluator returns generic `matched_claim_ids` that the backend maps to progression effects.

Example claims defined in `logic.json`:
- `claim_steward_possesses_testament`: steward possesses the hidden item
- `claim_steward_withholding`: steward is deliberately withholding it
- `claim_motive_control`: motive is preserving control over the estate

Unlock requires all three claims to be matched.

#### CharacterResponderInput
- `speaker`
- `player_utterance`
- `intent`
- `target`
- `matched_claim_ids`
- `state_snapshot`
- `response_constraints: { may_yield, may_deny, may_deflect, may_hint }`

---

## Response constraints derivation

### Who computes response_constraints

The evaluator does **not** compute `response_constraints`.
The responder does **not** derive them independently.

`response_constraints` are derived by a **constraint builder** in the backend (inside `game_service` or as a small dedicated helper).

### Derivation inputs

- `GameState` (current flags, cast state, steward_pressure)
- `ProgressEvaluatorOutput` (what the player just said)
- `logic.json` (the allowed rule model for the scenario)

### Flow

1. Evaluator says what the player input means
2. State updater updates truth/state
3. Constraint builder derives what the responder is allowed to do now
4. Responder receives constraints and obeys them

### Example rules

- Before unlock: `steward.may_deny = true`, `steward.may_deflect = true`, `steward.may_yield = false`
- After successful accusation: `steward.may_yield = true`, `steward.may_deny = false`

The constraint builder is the cleanest control surface between evaluation and response.

---

## Conversation history strategy

### Stage-1 approach

Conversation history is kept simple and bounded.

### Stored data

- **Recent raw turns**: last N turns (default: 4–6 turns)
- **Discovered topics**: explicit list of topic flags/IDs
- **Summary**: one short structured text, maintained deterministically by backend code

### No LLM summarization in stage 1

The summary is **not** generated by an LLM call.
It is updated deterministically by backend code from known events and discovered topics.

### Why

- Cheap and predictable
- Avoids prompt bloat
- Avoids extra LLM cost/latency
- Expandable later to real LLM-driven summarization

---

## Steward pressure model

### Purpose

`steward_pressure` is a small integer (e.g. 0–2) tracked in `conversation_state`.

### What increases it

Strong but incomplete accusations (significant claim matches that do not yet meet full unlock).

### What it affects in stage 1

- **Responder tone only**: as pressure increases, the steward becomes sharper, less patient, more defensive in dialogue
- **Suggested prompts**: pressure level may influence which example prompts are shown

### What it does NOT do

- It does **not** unlock the archive by itself
- Unlock still depends entirely on semantic claim matching

### Why keep it

- Keeps state meaningful and avoids dead state
- Avoids fake complexity
- Leaves room for later richer progression where pressure becomes a real progression signal

---

## Heir trust_level

### Removed from stage 1

`heir.trust_level` is **not** included in the stage-1 schema.

### Reason

The current scenario does not need trust gating. It adds schema complexity without gameplay value.

### Later

If alliance/trust mechanics are built in a later stage, `trust_level` can be reintroduced then.

---

## Todos and later-stage plans

These are **not** part of stage 1 implementation, but are deliberately noted as future directions.

### 1. Richer semantic progression model
The current prototype uses a simple unlock rule with evaluator isolation.

A later stage may expand this into a richer semantic progression model, for example tracking concepts such as:
- whether the player suspects the steward hid the testament
- whether the player understands the motive
- how cornered the steward feels

Purpose:
- less binary progression
- more LLM-native interaction feel

### 2. Event-driven schema evolution
Kept as a later-stage architecture option.

This would wrap evaluator/responder/state interactions into explicit events with an event log, such as:
- `EvaluationEvent`
- `StateChangeEvent`
- `CharacterResponseEvent`

Current plan does **not** use this yet.

### 3. Rich orchestration layer
Kept as a later-stage architecture option.

Current plan uses only a **thin coordinator**.

A later orchestration layer could coordinate things such as:
- evaluator selection
- response validation
- retries
- memory summarization
- consistency enforcement
- multi-step runtime policies

### 4. Meta-story generation layer
Kept as a later-stage architecture and product option.

This would create a game instance from a story schema instead of manually authoring each scenario.

It would generate and validate:
- cast
- locations
- story truth
- gate structure
- progression logic
- responder constraints

Important requirement:
Generated stories must remain **coherent and playable**, so validation is essential.

### 5. Frontend framework migration path
Current stage 1 uses plain JS + Vite.

A later migration to a heavier frontend framework such as React remains possible because the frontend is intentionally kept thin and the backend owns authoritative state.

### 6. Persistence / database later
Stage 1 intentionally avoids a DB.

Possible later evolution:
- persistent session storage
- save/load
- database-backed state
- analytics/history storage

---

## Stage-1 limitations and likely future solutions

### Limitation 1: very small story scope
Current prototype supports only a tiny authored scenario.

Why accepted now:
- needed to validate the core interaction loop

Possible later solution:
- richer scenario packages
- more states/gates
- multiple scenes and endings
- meta-story generation

### Limitation 2: simple progression rule
Current unlock logic is intentionally simple.

Why accepted now:
- fast validation of core product concept

Possible later solution:
- richer semantic evaluator
- multi-signal progression
- explicit pressure/trust/suspicion models

### Limitation 3: no persistence
Current runtime state is in memory only.

Why accepted now:
- avoids unnecessary complexity at prototype stage

Possible later solution:
- file snapshots
- DB-backed sessions
- save/load system

### Limitation 4: manual assets by default
Current visual assets are manual by default.

Why accepted now:
- strongest stability
- avoids image consistency complexity

Possible later solution:
- initialization-time asset generation
- controlled generated portrait/background pipeline
- hybrid asset packs

### Limitation 5: no rich orchestration
Current runtime uses a thin coordinator only.

Why accepted now:
- lower complexity
- easier to debug

Possible later solution:
- orchestration layer coordinating retries, validation, memory summarization, and policy routing

### Limitation 6: plain HTTP turn model
Current communication is one HTTP request per turn.

Why accepted now:
- simple and reliable

Possible later solution:
- streaming responses
- websocket session channel
- richer live UI behaviors

### Limitation 7: very light frontend
Current UI stack is intentionally minimal.

Why accepted now:
- focus effort on backend/game logic

Possible later solution:
- migrate to React or another richer frontend system

---

## Items intentionally deferred

These topics were discussed but intentionally not fully specified yet because they are lower priority than core runtime and content structure.

### Deferred topic 1: exact asset-class decisions
The hybrid asset approach is chosen, but exact rules for which assets/artifacts are authored vs generated are deferred.

### Deferred topic 2: exact payload shapes for HTTP endpoints
API route family is chosen, but exact request/response contracts are deferred.

### Deferred topic 3: exact contents of each scenario package file
The file set is locked, but each file's exact field-level content is not yet fully defined.

### Deferred topic 4: exact prompt templates
Prompt composition strategy is chosen, but the exact evaluator/responder prompt contents are not yet defined.

### Deferred topic 5: exact runtime contracts
The domain-shaped schema direction is chosen, but the exact strict contracts/types are not yet finalized.

---

## What should be decided next

The architecture and stack are now sufficiently stable to move into concrete implementation definition.

### Recommended next topic 1
**Exact contents of the scenario package files**

Why next:
- anchors the authored manor scenario on disk
- defines what the runtime loads
- naturally informs schema contracts and prompt composition

Concise suggestions for handling this:
- define each file one by one
- start with `story.json`, `characters.json`, `locations.json`, `logic.json`
- keep stage-1 contents minimal and scenario-specific in data, but generic in structure

### Recommended next topic 2
**Exact runtime contracts/schemas**

Why after package contents:
- contracts will be clearer once authored content shape is fixed

Concise suggestions:
- define `GameState` first
- then `ProgressEvaluatorOutput`
- then `ProgressEvaluatorInput`
- then `CharacterResponderInput`

### Recommended next topic 3
**Prompt composition structure**

Why after contracts:
- prompts should consume finalized scenario/runtime structures

Concise suggestions:
- define evaluator prompt layers first
- then steward responder layers
- then heir responder layers
- explicitly define what each role may and may not decide

### Recommended next topic 4
**Session initialization sequence in more detail**

Why later:
- depends on file contents and contracts

Concise suggestions:
- define load → validate → normalize → initialize state → compile context sequence
- keep it deterministic and inspectable

---

## Implementation guardrails

If another implementer or LLM starts from this document, the following guardrails should be respected:

- Do **not** let the LLM invent the story truth at runtime
- Do **not** let responder prompts independently decide progression
- Keep progression evaluation centralized
- Keep backend authoritative over all game truth
- Keep frontend thin
- Keep stage 1 minimal
- Prefer clean extensibility over premature complexity
- Represent the manor prototype as a **scenario package**, not as hardcoded one-off game logic everywhere
- Keep evaluator schema **generic / scenario-driven**, not manor-specific
- Derive response constraints in the backend via constraint builder, not in the evaluator or responder
- Narrator is template-driven in stage 1, not LLM-generated
- `prompt_context.json` must never contain truths not already in `story.json`
- Conversation history must stay bounded (last N turns + deterministic summary)

---

## Implementation-ready project folder structure

The structure below is intentionally aligned with the already chosen architecture:
- very light frontend
- minimal Python API backend
- layered backend module layout
- scenario-package-based content
- prompt templates in files
- structured trace files

This is a **stage-1 implementation structure**. It is intentionally small, explicit, and extendable.

```text
project-root/
  README.md
  .env
  .env.example
  .gitignore

  frontend/
    index.html
    vite.config.js
    package.json
    src/
      main.js
      api.js
      state.js
      render.js
      components/
        scene-view.js
        dialogue-panel.js
        prompt-suggestions.js
      styles/
        main.css

  backend/
    requirements.txt
    app/
      main.py

      api/
        routes.py
        dto.py

      core/
        config.py
        session_store.py
        trace_logger.py
        validators.py

      domain/
        game_state.py
        scenario_models.py
        progress_models.py
        response_models.py

      services/
        game_service.py
        session_initializer.py
        scenario_loader.py
        progress_evaluator.py
        character_responder.py
        state_updater.py
        constraint_builder.py
        prompt_loader.py
        prompt_builder.py

      ai/
        client.py
        evaluator_runner.py
        responder_runner.py

      prompts/
        evaluator/
          system.txt
          task.txt
          output_schema.json
        responder/
          common_system.txt
          steward_system.txt
          heir_system.txt
          task.txt
        narrator/
          scene_transition.txt
          archive_discovery.txt
          ending.txt

  scenarios/
    manor/
      story.json
      characters.json
      locations.json
      initial_state.json
      logic.json
      assets.json
      prompt_context.json
      generated/
      traces/

  assets/
    scenarios/
      manor/
        backgrounds/
        portraits/

  scripts/
    run_backend.sh
    run_frontend.sh
```

---

## File-by-file description

### Root files

#### `README.md`
**Purpose:** project overview and startup instructions.

**Important contents:**
- what the prototype is
- how to run frontend and backend
- where the manor scenario package lives
- how session state and traces work

---

#### `.env`
**Purpose:** local secret/config values.

**Important contents:**
- OpenAI API key
- model names if configurable
- optional debug flags

---

#### `.env.example`
**Purpose:** safe template for required environment variables.

**Important contents:**
- placeholder keys and config names

---

#### `.gitignore`
**Purpose:** ignore local/generated files.

**Important contents:**
- `.env`
- frontend build outputs
- Python cache files
- generated traces if not committed

---

## Frontend

The frontend is intentionally thin. It should not own game truth.

### `frontend/index.html`
**Purpose:** HTML shell for the SPA-like frontend.

**Important contents:**
- root container element
- script entrypoint
- minimal structure for scene, portrait, dialogue, input, suggestions

---

### `frontend/vite.config.js`
**Purpose:** Vite configuration.

**Important contents:**
- dev server config
- optional proxy to backend API during development

---

### `frontend/package.json`
**Purpose:** frontend dependencies and scripts.

**Important contents:**
- `dev`, `build`, `preview` scripts
- Vite dependency

---

### `frontend/src/main.js`
**Purpose:** frontend entrypoint.

**Defines:**
- startup/bootstrap flow
- initial session creation call
- event wiring between input UI and API client

**Important contents:**
- initialize frontend view state
- request a session from backend
- render first scene
- handle turn submission

---

### `frontend/src/api.js`
**Purpose:** minimal HTTP client for backend communication.

**Defines functions such as:**
- `createSession()`
- `submitTurn(sessionId, playerInput)`
- `getState(sessionId)`
- `resetSession(sessionId)`
- `getLatestTrace(sessionId)`

**Important contents:**
- fetch wrappers
- API endpoint paths
- JSON request/response handling
- basic error handling

---

### `frontend/src/state.js`
**Purpose:** frontend-only ephemeral view state.

**Defines:**
- small local state object or helpers for view state

**Important contents:**
- `inputText`
- `isSubmitting`
- `errorMessage`
- temporary rendered response cache
- selected/highlighted suggestion state if needed

This file must **not** hold authoritative game truth.

---

### `frontend/src/render.js`
**Purpose:** renders backend-provided state/turn output into the UI.

**Defines functions such as:**
- `renderApp(viewModel)`
- `renderScene(sceneData)`
- `renderDialogue(dialogueData)`
- `renderSuggestions(promptSuggestions)`

**Important contents:**
- DOM update logic
- composition of scene, portrait, dialogue, and suggestions

---

### `frontend/src/components/scene-view.js`
**Purpose:** renders background image and portrait area.

**Defines functions such as:**
- `renderSceneView(scene)`

**Important contents:**
- background image path handling
- portrait image path handling
- current location/character presentation

---

### `frontend/src/components/dialogue-panel.js`
**Purpose:** renders dialogue text and input area.

**Defines functions such as:**
- `renderDialoguePanel(dialogueState)`

**Important contents:**
- latest character response
- input box
- placeholder text: `Ask, inspect, accuse, or tell…`
- submit handling hooks

---

### `frontend/src/components/prompt-suggestions.js`
**Purpose:** renders the 3 small context-sensitive example prompts.

**Defines functions such as:**
- `renderPromptSuggestions(suggestions)`

**Important contents:**
- suggestion list rendering
- click-to-fill or click-to-submit behavior

---

### `frontend/src/styles/main.css`
**Purpose:** visual styling.

**Important contents:**
- scene layout
- portrait placement
- dialogue panel styling
- prompt suggestion styling

---

## Backend

### `backend/requirements.txt`
**Purpose:** Python dependencies.

**Important contents:**
- FastAPI
- Uvicorn
- OpenAI SDK
- Pydantic
- python-dotenv or equivalent

---

### `backend/app/main.py`
**Purpose:** backend entrypoint.

**Defines:**
- FastAPI app creation
- route registration
- startup wiring

**Important contents:**
- instantiate config
- instantiate session store
- instantiate services if needed
- include API routes

---

## Backend API layer

### `backend/app/api/routes.py`
**Purpose:** HTTP route definitions.

**Defines endpoints:**
- `POST /sessions`
- `POST /sessions/{session_id}/turns`
- `POST /sessions/{session_id}/reset`
- `GET /sessions/{session_id}/state`
- `GET /sessions/{session_id}/traces/latest`

**Important contents:**
- route handlers
- mapping between HTTP DTOs and service calls
- error translation

---

### `backend/app/api/dto.py`
**Purpose:** API request/response DTOs.

**Defines classes/models such as:**
- `CreateSessionRequest`
- `CreateSessionResponse`
- `SubmitTurnRequest`
- `SubmitTurnResponse`
- `GetStateResponse`
- `TraceResponse`

**Important contents:**
- Pydantic request/response shapes
- external API contracts only

---

## Backend core utilities

### `backend/app/core/config.py`
**Purpose:** runtime configuration loading.

**Defines classes/functions such as:**
- `Settings`
- `get_settings()`

**Important contents:**
- API key
- model names
- scenario root path
- trace output path
- debug flags

---

### `backend/app/core/session_store.py`
**Purpose:** in-memory authoritative session map.

**Defines classes/functions such as:**
- `SessionStore`
- `create_session(game_state)`
- `get_session(session_id)`
- `update_session(session_id, game_state)`
- `reset_session(session_id, game_state)`

**Important contents:**
- dictionary keyed by session ID
- storage of current `GameState`
- `last_accessed_at` timestamp per session for TTL cleanup

---

### `backend/app/core/trace_logger.py`
**Purpose:** structured debug traces per session/turn.

**Defines classes/functions such as:**
- `TraceLogger`
- `write_trace(session_id, turn_index, trace_payload)`
- `read_latest_trace(session_id)`

**Important contents:**
- JSON file output
- per-session/per-turn trace file naming
- evaluator/responder/state diff trace format

---

### `backend/app/core/validators.py`
**Purpose:** lightweight startup validation for scenario packages.

**Defines functions such as:**
- `validate_scenario_package(path)`
- `validate_required_files(...)`
- `validate_asset_references(...)`
- `validate_logic_references(...)`

**Important contents:**
- checks for missing files
- checks for missing referenced character/location/asset IDs
- checks for basic package integrity

---

## Backend domain models

### `backend/app/domain/game_state.py`
**Purpose:** authoritative runtime state models.

**Defines classes/models such as:**
- `GameState`
- `LocationState`
- `FlagsState`
- `ConversationState`
- `CastState`

**Important contents:**
- current location
- addressed character
- archive unlocked flag
- game finished flag
- conversation summary
- discovered topics
- recent raw turns (last N)
- steward pressure level
- steward/heir runtime state (available, yielded)
- available characters and exits (derived)

---

### `backend/app/domain/scenario_models.py`
**Purpose:** models representing authored scenario package content.

**Defines classes/models such as:**
- `StoryTruth`
- `CharacterDefinition`
- `LocationDefinition`
- `ScenarioLogic`
- `AssetManifest`
- `PromptContextDefinition`
- possibly `ScenarioPackage`

**Important contents:**
- structured representation of scenario JSON files
- IDs and references between authored content files

---

### `backend/app/domain/progress_models.py`
**Purpose:** evaluator-related structured models.

**Defines classes/models such as:**
- `ProgressEvaluatorInput`
- `ProgressEvaluatorOutput`
- `SemanticFindings`
- `StateEffects`

**Important contents:**
- player utterance
- addressed character
- generic matched claim IDs
- unlock decision
- pressure/topic effects

---

### `backend/app/domain/response_models.py`
**Purpose:** responder-related structured models and possibly turn output view models.

**Defines classes/models such as:**
- `CharacterResponderInput`
- `ResponseConstraints`
- `TurnResultViewModel`

**Important contents:**
- speaker
- intent
- matched claim IDs
- state snapshot
- response constraints
- output data needed by frontend rendering

---

## Backend services

### `backend/app/services/game_service.py`
**Purpose:** thin application-level coordinator for a gameplay turn.

**Defines functions/classes such as:**
- `GameService`
- `create_session(...)`
- `submit_turn(session_id, player_input)`
- `reset_session(session_id)`
- `get_state(session_id)`

**Important contents:**
- orchestrates evaluator → state update → constraint builder → responder → trace write
- should remain thin and explicit

---

### `backend/app/services/session_initializer.py`
**Purpose:** prepared session flow implementation.

**Defines functions such as:**
- `initialize_session(scenario_id)`

**Important contents:**
- load scenario package
- validate scenario package
- derive any normalized runtime data
- load prompt context
- create initial `GameState`

---

### `backend/app/services/scenario_loader.py`
**Purpose:** loads scenario package files from disk.

**Defines functions/classes such as:**
- `ScenarioLoader`
- `load_story(...)`
- `load_characters(...)`
- `load_locations(...)`
- `load_logic(...)`
- `load_assets(...)`
- `load_prompt_context(...)`
- `load_scenario_package(scenario_id)`

**Important contents:**
- JSON file reading
- mapping into scenario domain models

---

### `backend/app/services/progress_evaluator.py`
**Purpose:** domain-level progression decision boundary.

**Defines functions/classes such as:**
- `ProgressEvaluator`
- `evaluate(player_utterance, game_state, scenario_package)`

**Important contents:**
- creation of `ProgressEvaluatorInput`
- call to evaluator AI runner
- interpretation of structured evaluator result
- no direct state mutation here

This file is the central place where progression meaning is evaluated.

---

### `backend/app/services/character_responder.py`
**Purpose:** domain-level character response boundary.

**Defines functions/classes such as:**
- `CharacterResponder`
- `respond(game_state, evaluator_output, player_utterance)`

**Important contents:**
- decide active speaker
- build `CharacterResponderInput`
- call responder AI runner
- return natural dialogue output plus any frontend-facing turn data

This file must not decide progression on its own.

---

### `backend/app/services/state_updater.py`
**Purpose:** apply evaluator effects to authoritative `GameState`.

**Defines functions/classes such as:**
- `StateUpdater`
- `apply_progress(game_state, evaluator_output)`
- `apply_end_conditions(game_state, scenario_logic)`

**Important contents:**
- flips `archive_unlocked`
- updates conversation state
- updates yielded state
- updates game finished flag when appropriate

---

### `backend/app/services/constraint_builder.py`
**Purpose:** derives response constraints from current state, evaluator output, and scenario logic.

**Defines functions/classes such as:**
- `ConstraintBuilder`
- `build_constraints(game_state, evaluator_output, scenario_logic)`

**Important contents:**
- reads `logic.json` constraint rules
- maps current state + evaluator result into `ResponseConstraints`
- e.g. before unlock: `may_deny=true, may_yield=false`; after unlock: `may_yield=true, may_deny=false`
- this is the control surface between evaluation and response

---

### `backend/app/services/prompt_loader.py`
**Purpose:** load prompt template files from disk.

**Defines functions/classes such as:**
- `PromptLoader`
- `load_evaluator_templates()`
- `load_responder_templates()`

**Important contents:**
- reads text templates
- loads evaluator output schema file

---

### `backend/app/services/prompt_builder.py`
**Purpose:** layered prompt composition.

**Defines functions/classes such as:**
- `PromptBuilder`
- `build_evaluator_prompt(...)`
- `build_steward_prompt(...)`
- `build_heir_prompt(...)`

**Important contents:**
- combines base system templates
- role templates
- scenario context
- turn context
- runtime constraints

This file is important because prompt layering was an explicit architectural decision.

---

## Backend AI integration layer

### `backend/app/ai/client.py`
**Purpose:** internal OpenAI Responses API wrapper.

**Defines classes/functions such as:**
- `AIClient`
- `run_structured(...)`
- `run_text(...)`

**Important contents:**
- OpenAI client initialization
- evaluator structured output calls
- responder natural-text calls
- role-specific model config support

---

### `backend/app/ai/evaluator_runner.py`
**Purpose:** evaluator-specific model execution wrapper.

**Defines functions/classes such as:**
- `EvaluatorRunner`
- `run_evaluator(prompt, schema, role_config)`

**Important contents:**
- calls `AIClient` with structured output expectations
- returns typed evaluator result

---

### `backend/app/ai/responder_runner.py`
**Purpose:** responder-specific model execution wrapper.

**Defines functions/classes such as:**
- `ResponderRunner`
- `run_responder(prompt, role_config)`

**Important contents:**
- calls `AIClient` for natural text output
- may support separate role config for steward/heir later

---

## Prompt files

### `backend/app/prompts/evaluator/system.txt`
**Purpose:** evaluator base system prompt.

**Important contents:**
- evaluator role definition
- instruction to interpret, not dramatize
- instruction to stay within scenario truth
- instruction to output only structured result

---

### `backend/app/prompts/evaluator/task.txt`
**Purpose:** evaluator task-layer template.

**Important contents:**
- placeholders for player utterance
- current scene
- scenario truth
- conversation summary
- current flags
- output instructions

---

### `backend/app/prompts/evaluator/output_schema.json`
**Purpose:** structured output schema for evaluator.

**Important contents:**
- exact JSON schema expected from evaluator model

---

### `backend/app/prompts/responder/common_system.txt`
**Purpose:** shared responder base prompt.

**Important contents:**
- responder should speak in character
- responder must not invent new world truth
- responder must obey constraints and game state
- responder must not decide progression independently

---

### `backend/app/prompts/responder/steward_system.txt`
**Purpose:** steward-specific character prompt.

**Important contents:**
- steward personality
- defensive posture
- lies/deflections allowed before being cornered
- yielding behavior when state allows it

---

### `backend/app/prompts/responder/heir_system.txt`
**Purpose:** heir-specific character prompt.

**Important contents:**
- heir personality
- suspicion posture
- what the heir may hint at
- what the heir does not actually know as fact

---

### `backend/app/prompts/responder/task.txt`
**Purpose:** responder task-layer template.

**Important contents:**
- player utterance
- selected speaker
- matched claim IDs
- response constraints
- current scene/context

---

### `backend/app/prompts/narrator/scene_transition.txt`
**Purpose:** narrator template for location transitions.

**Important contents:**
- template text for moving between locations
- placeholder for location name/description

---

### `backend/app/prompts/narrator/archive_discovery.txt`
**Purpose:** narrator template for testament discovery scene.

**Important contents:**
- template text describing entering the archive and finding the testament

---

### `backend/app/prompts/narrator/ending.txt`
**Purpose:** narrator template for game ending.

**Important contents:**
- template text for the resolution/ending narration

---

## Scenario packages

### `scenarios/manor/story.json`
**Purpose:** narrative core of the scenario.

**Important contents:**
- scenario ID and title
- premise
- hidden story truth summary
- ending summary
- high-level narrative description

---

### `scenarios/manor/characters.json`
**Purpose:** authored character definitions.

**Important contents:**
- steward and heir IDs
- names
- roles
- personality summaries
- knowledge boundaries
- portrait asset references

---

### `scenarios/manor/locations.json`
**Purpose:** authored location definitions.

**Important contents:**
- study and archive IDs
- descriptions
- background asset references
- visible context text if needed

---

### `scenarios/manor/initial_state.json`
**Purpose:** initial runtime state seed.

**Important contents:**
- starting location
- initial flags
- initial conversation state
- initial cast state

---

### `scenarios/manor/logic.json`
**Purpose:** progression and resolution logic description.

**Important contents:**
- defined claims with IDs and semantic descriptions
- gate conditions specifying which claim IDs are required for unlock
- end condition (enter archive after unlock)
- constraint rules mapping state/evaluator result to response constraints
- any relevant runtime rule descriptions

This file should describe the game logic for the scenario, without burying it inside story prose.
Claim definitions here are what make the evaluator schema generic.

---

### `scenarios/manor/assets.json`
**Purpose:** asset manifest.

**Important contents:**
- mapping from character/location IDs to image files
- optional generated/manual asset metadata

---

### `scenarios/manor/prompt_context.json`
**Purpose:** scenario-specific prompt support context.

**Important contents:**
- wording/style hints
- scenario-specific vocabulary
- scenario truth restatements for prompt composition
- optional example prompt suggestions per context

---

### `scenarios/manor/generated/`
**Purpose:** reserved output folder for later or optional generated artifacts.

**Possible contents later:**
- normalized scenario data
- compiled prompt context bundles
- generated images

For stage 1 it may exist but remain lightly used.

---

### `scenarios/manor/traces/`
**Purpose:** optional scenario-local trace output location if traces are organized by scenario.

**Possible contents:**
- session/turn trace JSON files

If traces are instead stored globally elsewhere, this folder can remain unused initially.

---

## Assets

### `assets/scenarios/manor/backgrounds/`
**Purpose:** background scene images.

**Important contents:**
- study background
- archive background

---

### `assets/scenarios/manor/portraits/`
**Purpose:** character bust portrait images.

**Important contents:**
- steward bust portrait
- heir bust portrait

---

## Scripts

### `scripts/run_backend.sh`
**Purpose:** convenience startup script for backend.

**Important contents:**
- environment loading if desired
- FastAPI/Uvicorn startup command

---

### `scripts/run_frontend.sh`
**Purpose:** convenience startup script for frontend.

**Important contents:**
- Vite dev server startup command

---

## Minimum implementation order suggestion

A clean implementation order from this structure would be:

1. scenario files with minimal manor data
2. backend domain models
3. scenario loader + validators
4. session store + session initializer
5. prompt loader + prompt builder
6. AI client + evaluator runner + responder runner
7. progress evaluator + state updater + character responder
8. game service
9. API DTOs + routes
10. thin frontend rendering and input flow

---

## Handoff summary

This project is a **minimal LLM-driven adventure game prototype** with:
- one tiny authored manor scenario
- two characters (steward, heir) plus a template-driven narrator
- two locations (study, archive) with archive gated behind unlock
- one semantic confrontation gate using generic scenario-driven claim matching
- one ending (yield → move to archive → narrator discovery → game end)
- free-text player interaction with UI-driven addressee and movement support
- isolated progression evaluator with generic claim-based findings
- separate character responder with backend-derived response constraints
- constraint builder deriving responder permissions from state + logic + evaluator
- FastAPI backend with CORS, static asset serving, and session TTL cleanup
- plain JS + Vite frontend with unified loading state
- OpenAI Responses API integration (not Chat Completions)
- structured evaluator outputs, natural text responder outputs
- template-driven narrator (no LLM call)
- manual assets by default, served via FastAPI
- scenario package based content loading with generic evaluator schema
- conversation memory: last N turns + backend summary + discovered topics
- steward pressure model (flavor only, does not unlock)
- no heir.trust_level in stage 1
- LLM failure handling with retry-once + safe fallback
- no database; in-memory session state with TTL

The next concrete work should begin with:
1. exact contents of the scenario package files (including generic claims in logic.json)
2. exact runtime contracts
3. exact prompt composition structure

This is the complete current design baseline.

