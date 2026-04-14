from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router, set_game_service
from backend.app.core.config import get_settings
from backend.app.core.session_store import SessionStore
from backend.app.core.trace_logger import TraceLogger
from backend.app.services.constraint_builder import ConstraintBuilder
from backend.app.services.game_service import GameService
from backend.app.services.scenario_loader import ScenarioLoader
from backend.app.services.session_initializer import SessionInitializer
from backend.app.services.state_updater import StateUpdater

app = FastAPI(title="Adventure Game", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets if the directory exists
assets_path = Path("assets")
if assets_path.is_dir():
    app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

# Wire up services
settings = get_settings()
store = SessionStore()
loader = ScenarioLoader(base_path=settings.scenario_root_path)
initializer = SessionInitializer(loader=loader, store=store)
state_updater = StateUpdater()
constraint_builder = ConstraintBuilder()

# --- Prompt templates (always loaded — narrator text is authored content, not AI) ---
from backend.app.services.prompt_builder import PromptBuilder
from backend.app.services.prompt_loader import PromptLoader

prompt_loader = PromptLoader()
prompt_builder = PromptBuilder(
    evaluator_templates=prompt_loader.load_evaluator_templates(),
    responder_templates=prompt_loader.load_responder_templates(),
    narrator_templates=prompt_loader.load_narrator_templates(),
)

# --- LLM services (optional — gracefully degrades to mocks if no API key) ---
progress_evaluator = None
character_responder = None
trace_logger = None

if settings.openai_api_key:
    from backend.app.ai.client import AIClient
    from backend.app.ai.evaluator_runner import EvaluatorRunner
    from backend.app.ai.responder_runner import ResponderRunner
    from backend.app.services.character_responder import CharacterResponder
    from backend.app.services.progress_evaluator import ProgressEvaluator

    ai_client = AIClient(
        api_key=settings.openai_api_key,
        evaluator_model=settings.evaluator_model,
        responder_model=settings.responder_model,
    )
    evaluator_runner = EvaluatorRunner(ai_client)
    responder_runner = ResponderRunner(ai_client)
    progress_evaluator = ProgressEvaluator(prompt_builder, evaluator_runner)
    character_responder = CharacterResponder(prompt_builder, responder_runner)

if settings.trace_output_path:
    trace_logger = TraceLogger(base_path=settings.trace_output_path)

game_service = GameService(
    store=store,
    initializer=initializer,
    state_updater=state_updater,
    constraint_builder=constraint_builder,
    progress_evaluator=progress_evaluator,
    character_responder=character_responder,
    prompt_builder=prompt_builder,
    trace_logger=trace_logger,
    asset_base_url=settings.asset_base_url,
)
set_game_service(game_service)

app.include_router(router, prefix="/api")


def _check_scenario_assets() -> None:
    """Log warnings at startup for referenced asset files that don't exist on disk."""
    assets_root = Path("assets")
    for scenario_dir in settings.scenario_root_path.iterdir():
        if not scenario_dir.is_dir():
            continue
        try:
            pkg = loader.load_scenario_package(scenario_dir.name)
        except Exception:
            continue
        for path in list(pkg.assets.portraits.values()) + list(pkg.assets.backgrounds.values()):
            full = assets_root / path
            if not full.exists():
                print(
                    f"WARNING: Asset file missing: {full}  "
                    f"(referenced in {scenario_dir.name}/assets.json). "
                    f"Run 'python -m tools.generate_assets {scenario_dir.name}' to generate."
                )


_check_scenario_assets()


@app.middleware("http")
async def cleanup_expired_sessions(request: Request, call_next):
    """Periodically clean up expired sessions on each request."""
    store.cleanup_expired(max_age_minutes=60)
    return await call_next(request)
