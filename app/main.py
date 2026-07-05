import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.activity import router as activity_router
from app.api.auth import router as auth_router
from app.api.brand_kit import router as brand_kit_router
from app.api.clients import router as clients_router
from app.api.dashboard import router as dashboard_router
from app.api.images import router as images_router
from app.api.jobs import router as jobs_router
from app.api.settings import router as settings_router
from app.core.config import settings
from app.database.session import Base, engine

from app.models import admin, client, job, setting, activity, image_generation, brand_kit  # noqa: F401

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

# Create static directory for generated images
os.makedirs("static/images", exist_ok=True)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend for Wayne E Solutions AI Video Studio",
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global error handler ───────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )

# ── Routers ───────────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth_router)
app.include_router(clients_router)
app.include_router(jobs_router)
app.include_router(dashboard_router)
app.include_router(settings_router)
app.include_router(images_router)
app.include_router(activity_router)
app.include_router(brand_kit_router)

# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
