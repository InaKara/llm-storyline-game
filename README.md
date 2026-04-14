# Adventure Game Prototype

A text-based interactive mystery game with LLM-powered characters. Built with **FastAPI** (backend) and **vanilla JavaScript** (frontend).

## The Game

You arrive at a manor where an important testament has gone missing. Through dialogue with the steward and heir, you uncover the truth, unlock the archive, and retrieve the hidden document.

- **Free-text input** — ask questions, make accusations, inspect the environment
- **Two characters** — a guarded steward (who knows the truth) and a suspicious heir
- **Progression gates** — match specific claims to unlock new locations
- **LLM responses** — GPT-4o evaluates player intent, GPT-4o-mini generates in-character dialogue

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 18+ (for frontend)
- OpenAI API key (optional — game works with mock responses without it)

### Backend

```bash
uv sync
echo "OPENAI_API_KEY=sk-..." > .env   # optional
uv run uvicorn backend.app.main:app --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

### Generate Assets (optional)

Replace placeholder SVGs with AI-generated PNGs. Requires `OPENAI_API_KEY` in `.env`.

```bash
uv run python -m tools.generate_assets manor
uv run python -m tools.generate_assets manor --force   # regenerate all
```

### Tests

```bash
uv run pytest          # backend (99 tests)
cd frontend && npm test  # frontend (18 tests)
```

## Architecture

```
Browser (5173) ──Vite proxy──▶ FastAPI (8000) ──▶ OpenAI API
                               ├─ routes.py → GameService → pipeline
                               └─ StaticFiles(/assets)
```

## Project Structure

```
backend/app/
  api/          routes.py, dto.py
  core/         config.py, session_store.py, trace_logger.py
  domain/       game_state.py, scenario_models.py, progress_models.py, response_models.py
  services/     game_service.py, state_updater.py, constraint_builder.py, ...
  ai/           ai_client.py, evaluator_runner.py, responder_runner.py
  prompts/      evaluator/, responder/, narrator/ templates

frontend/src/
  main.js, render.js, api.js, state.js
  components/   scene-view.js, dialogue-panel.js, prompt-suggestions.js

scenarios/manor/   story.json, characters.json, locations.json, logic.json, ...
tools/             generate_assets.py, prompts/
docs/              implementation plans, phase explanations
```
