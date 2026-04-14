# Phase 6 — Frontend

## What This Phase Does

Phase 6 adds a browser-based UI for playing the game. Instead of using `curl` or `Invoke-RestMethod`, you now open `http://localhost:5173` in a browser and interact with a visual dialogue interface.

The frontend is **thin** — plain JavaScript, no framework. All game logic stays on the backend. The frontend only does three things:

1. Calls the backend API
2. Stores ephemeral UI state (is the input disabled? what's the current response?)
3. Renders HTML from that state

---

## Architecture Decisions

### Why no React/Vue/Svelte?

The implementation plan deliberately uses plain JavaScript to teach:
- How the DOM works without abstraction
- Manual rendering cycles (state changes → re-render the whole UI)
- How fetch-based API communication works without wrappers

This makes the frontend easy to understand and requires zero build-time complexity beyond Vite's dev server.

### Why Vite?

Vite provides two critical features:
- **Hot module reload** — change CSS or JS, browser updates instantly
- **Proxy** — requests to `/api/*` and `/assets/*` are forwarded to `http://localhost:8000`, avoiding CORS issues entirely during development

The `vite.config.js` is only 10 lines.

### Rendering strategy

Without a framework, the frontend uses a "re-render everything" approach. After each state change (turn submitted, character switched, reset), the entire UI is rebuilt from scratch. This is simple and correct, though not optimal for large UIs. For a dialogue game with one scene and one text panel, it's perfectly adequate.

---

## File-by-File Walkthrough

### 1. Vite Project Setup — `frontend/package.json` + `frontend/vite.config.js` + `frontend/index.html`

The `package.json` declares a single dev dependency: Vite. Three scripts:
- `dev` — starts the dev server on port 5173
- `build` — produces a production bundle in `dist/`
- `preview` — serves the production build locally

The `vite.config.js` configures the proxy:
```javascript
proxy: {
  '/api': 'http://localhost:8000',
  '/assets': 'http://localhost:8000',
}
```

When the browser requests `/api/sessions`, Vite intercepts it and forwards to the FastAPI backend. The browser never sees a cross-origin request.

The `index.html` is a minimal shell: a `<div id="app">` and a script tag pointing to `src/main.js`.

### 2. API Client — `frontend/src/api.js`

A small module of `fetch` wrappers. All HTTP communication goes through here — no scattered `fetch()` calls elsewhere.

```javascript
export function createSession() { ... }
export function submitTurn(sessionId, playerInput) { ... }
export function getState(sessionId) { ... }
export function resetSession(sessionId) { ... }
export function switchCharacter(sessionId, characterId) { ... }
export function move(sessionId, targetLocation) { ... }
```

Each function calls the appropriate `/api/...` endpoint, parses JSON, and returns the result. The shared `request()` helper throws on non-2xx responses.

**Why a dedicated API module:** Same reason as the backend's `AIClient` wrapper — isolation. If the API shape changes, only this file changes. URL construction uses `encodeURIComponent()` for the session ID to prevent injection.

### 3. View State — `frontend/src/state.js`

Five fields:
- `sessionId` — the active session UUID
- `isSubmitting` — true while waiting for an API response (disables input)
- `currentTurn` — the latest response from the backend (contains speaker, dialogue, location, suggestions, etc.)
- `inputText` — what's currently typed in the input field
- `errorMessage` — shown when an API call fails

This is **not** game truth. It's ephemeral UI state. The backend is the source of truth — the frontend just mirrors what it last received.

### 4. Scene View — `frontend/src/components/scene-view.js`

Renders the top half of the screen:
- **Background image** — set via CSS `background-image` from `turnData.background_url`
- **Location label** — "study", "archive", etc. positioned at top-left
- **Character portrait** — positioned at bottom-right, with an `onerror` handler to hide if the image fails to load
- **Character buttons** — "steward" / "heir" at top-right, highlighting the currently-addressed character

Clicking a character button triggers `onCharacterClick`, which calls `PUT /api/sessions/{id}/addressed-character`.

### 5. Dialogue Panel — `frontend/src/components/dialogue-panel.js`

Renders the bottom section:
- **Speaker name** — styled differently for narrator (gold italic) vs character (gold bold)
- **Dialogue text** — the actual response from the LLM or narrator
- **Error message** — red background, shown when API calls fail
- **Text input** — disabled during submission, auto-focused after render
- **Submit button** — shows "Thinking…" while waiting
- **Game finished state** — hides the input and shows "The story has reached its conclusion."

The input is a `<form>` so pressing Enter submits. The form's `submit` event is intercepted to prevent page reload.

### 6. Prompt Suggestions — `frontend/src/components/prompt-suggestions.js`

Renders up to 3 clickable pill-shaped buttons below the input. The suggestions come from the backend's `suggestions` field, which changes based on game progress (start → mid_game → post_unlock).

Clicking a suggestion immediately submits it as player input.

### 7. Renderer — `frontend/src/render.js`

The top-level function that composes everything. Called after every state change:

```
renderApp(turnData, viewState, callbacks)
  ├── renderSceneView()
  ├── renderDialoguePanel()
  ├── renderSuggestions()
  ├── exits bar (movement buttons)
  └── toolbar (restart button)
```

The exits bar renders location buttons ("archive") when `available_exits` is non-empty. These fire a `go to {location}` command, which the `main.js` routing logic detects as movement.

### 8. Main Entrypoint — `frontend/src/main.js`

Bootstrap flow:
1. Show "Starting adventure…" loading text
2. Call `createSession()` — API responds with narrator opening
3. Store session ID and turn data in state
4. Render the full UI

Event handling:
- **Submit** — checks if the text matches a movement pattern (same regex as the backend). If it does and the target is a valid exit, calls `move()` instead of `submitTurn()`. Otherwise submits as a normal turn.
- **Character click** — calls `switchCharacter()` and re-renders
- **Suggestion click** — fills input text and submits
- **Reset** — calls `resetSession()` and re-renders

The movement regex mirrors the backend's `_MOVEMENT_RE`:
```javascript
const MOVEMENT_RE = /^(?:go\s+(?:to\s+)?|move\s+(?:to\s+)?|walk\s+(?:to\s+)?|enter\s+|head\s+(?:to\s+)?)(.+)$/i;
```

### 9. Styling — `frontend/src/styles/main.css`

CSS custom properties define the color scheme:
- Dark navy background (`#1a1a2e`)
- Gold accent (`#c9a959`) for speaker names, narrator text, and buttons
- Serif font (Georgia) for the Victorian era feel

Layout:
- `#app` is a vertical flexbox filling the viewport, capped at 960px wide
- Scene area flexes to fill available height (min 200px)
- Dialogue panel, suggestions, exits, and toolbar stack below

The scene background uses `background-size: cover` so any image fills the space. Portraits are absolutely positioned with a drop shadow.

---

## Placeholder Assets

Four SVG files provide visual placeholders:

- `assets/scenarios/manor/portraits/steward.svg` — silhouette with "Mr. Hargrove" label
- `assets/scenarios/manor/portraits/heir.svg` — silhouette with "Lady Ashworth" label
- `assets/scenarios/manor/backgrounds/study.svg` — simplified study scene (desk, bookshelf, window)
- `assets/scenarios/manor/backgrounds/archive.svg` — simplified archive (shelves, archway, scroll on pedestal)

These are hand-drawn SVG — no external dependencies. They work immediately and can be replaced with AI-generated images later.

The `scenarios/manor/assets.json` maps character/location IDs to file paths, and the `GameService._background_url()` / `._portrait_url()` methods prepend the `asset_base_url` setting (`/assets` by default) to construct the full URL served by FastAPI's `StaticFiles` mount.

---

## Pre-Prompt Compliance Fix

Before starting the frontend, we also fixed the steward's prompt to prevent LLM non-compliance with `may_deny: false`:

**Prompt changes:**
- `responder/common_system.txt` — added explicit rules: "A constraint set to false is an absolute prohibition", "When may_deny=false, you MUST NOT deny", "When may_yield=true and may_deny=false, you MUST acknowledge the truth"
- `responder/steward_system.txt` — added negative constraint instructions for `may_deny=false` and a combined `may_yield=true AND may_deny=false` rule

**Code change:**
- `state_updater.py` — when a gate fires (all required claims matched), pressure is now maxed out (`steward_pressure = max_pressure`). This aligns the behavior guide ("Pressure 2: cornered, may slip into justifications") with the yield constraint, giving the LLM consistent signals.

---

## How to Play

1. **Start the backend:** `uv run uvicorn backend.app.main:app --port 8000`
2. **Start the frontend:** `cd frontend && npm run dev`
3. **Open browser:** `http://localhost:5173`

You'll see the study scene with the narrator's opening text. Type questions, accusations, or click suggestions. The steward and heir respond via LLM (or mock responses if no API key is set).

---

## What's Different from Phases 1-5

| Aspect | Phases 1–5 | Phase 6 |
|--------|-----------|---------|
| Interaction | curl / PowerShell | Browser UI |
| Visual | JSON responses | Scene + portrait + dialogue |
| Suggestions | In response JSON | Clickable buttons |
| Movement | POST body | Click exit buttons or type "go to archive" |
| Character switching | PUT endpoint | Click character name |

---

## Testing

Vitest with jsdom provides 18 frontend unit tests across 4 test files:

- `tests/scene-view.test.js` (6 tests) — background, location label, portrait rendering, portrait null-hiding, active character highlighting via `addressedCharacter` state (not speaker name), character click callback
- `tests/dialogue-panel.test.js` (6 tests) — speaker/dialogue rendering, narrator styling, disabled input during submission, error message display, game-finished state, form submit callback
- `tests/suggestions.test.js` (3 tests) — renders up to 3 buttons, click callback, empty suggestions
- `tests/render.test.js` (3 tests) — all sections rendered, exit buttons call `onMove` directly (not synthesized text), game-finished hides suggestions/exits

Run frontend tests: `cd frontend && npm test`

Manual verification checklist:

- ✅ Vite dev server starts on port 5173
- ✅ Proxy forwards `/api` and `/assets` to FastAPI
- ✅ Session creation renders narrator opening
- ✅ Background SVGs and portrait SVGs load
- ✅ Character switching highlights the active character
- ✅ Suggestions render and are clickable
- ✅ Exit buttons appear when `available_exits` is non-empty
- ✅ "Thinking…" state while waiting for LLM response
- ✅ Game-finished state hides input and shows conclusion text
- ✅ Reset button restarts the game

All 99 backend tests + 18 frontend tests pass.

---

## Review Fixes

### Fix 1 (High): Character switching corrupts displayed turn

**Problem:** After switching characters, `main.js` overwrote `currentTurn.speaker` with the raw character ID, falsifying the transcript. The active-button logic in `scene-view.js` compared the last speaker string (e.g. "Mr. Hargrove") against character IDs ("steward"), which never matched.

**Fix:**
- Added `addressedCharacter` to view state (`state.js`)
- `handleCharacterClick` now reads `addressed_character` from the backend's `SessionStateResponse` instead of mutating `currentTurn.speaker`
- `scene-view.js` now takes `viewState` and uses `viewState.addressedCharacter === charId` for active highlighting
- `init` and `handleReset` set `addressedCharacter` from `available_characters[0]`

### Fix 2 (Medium): Movement handling drift between frontend and backend

**Problem:** The frontend had its own movement regex (looser than the backend's) and only fast-pathed when the typed target exactly matched a lowered exit ID. The backend also resolves location names and partial matches. Exit buttons synthesized free text via `onSubmit("go to archive")` instead of calling the move API.

**Fix:**
- Removed the frontend movement regex entirely — all free-text input goes through `submitTurn()`, letting the backend classify movement vs dialogue
- Added `handleMove(locationId)` that calls the explicit `move()` API
- Exit buttons in `render.js` now call `onMove(exit)` directly instead of synthesizing text
- Added `onMove` to the callback interface

### Fix 3 (Medium-Low): No frontend test coverage

**Problem:** All 3 frontend bugs shipped behind a fully green backend test suite. No tests exercised the UI state synchronization logic.

**Fix:** Added Vitest + jsdom with 18 tests across 4 files:
- `scene-view.test.js` — verifies active character highlighting uses `addressedCharacter`, not speaker
- `dialogue-panel.test.js` — verifies input disabling, error display, game-finished state
- `suggestions.test.js` — verifies rendering and click callbacks
- `render.test.js` — verifies exit buttons call `onMove` directly, not `onSubmit`
