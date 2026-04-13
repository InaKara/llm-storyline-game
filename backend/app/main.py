from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router, set_game_service
from backend.app.core.config import get_settings
from backend.app.core.session_store import SessionStore
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
game_service = GameService(
    store=store,
    initializer=initializer,
    state_updater=state_updater,
    constraint_builder=constraint_builder,
)
set_game_service(game_service)

app.include_router(router, prefix="/api")


@app.middleware("http")
async def cleanup_expired_sessions(request: Request, call_next):
    """Periodically clean up expired sessions on each request."""
    store.cleanup_expired(max_age_minutes=60)
    return await call_next(request)
