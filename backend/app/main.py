from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router

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

app.include_router(router, prefix="/api")
