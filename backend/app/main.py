"""
Research Tinder — FastAPI main application.
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db
from app.routes.papers import router as papers_router
from app.routes.settings import router as settings_router
from app.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Research Tinder...")
    await init_db()
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()
    logger.info("Research Tinder shut down.")


app = FastAPI(
    title="Research Tinder",
    description="Swipe through arXiv papers matched to your interests by a local LLM",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the frontend dev server and any localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(papers_router)
app.include_router(settings_router)


@app.get("/api/ping")
async def ping():
    return {"message": "pong", "app": "Research Tinder"}


# Serve React build in production (if static/ directory exists)
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            response = FileResponse(file_path)
            # Service worker must never be cached by the browser
            if full_path in ("sw.js", "registerSW.js", "manifest.webmanifest"):
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                if full_path == "sw.js":
                    response.headers["Service-Worker-Allowed"] = "/"
            return response
        return FileResponse(STATIC_DIR / "index.html")
