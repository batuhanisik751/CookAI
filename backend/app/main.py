from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.recipes import router as recipes_router
from app.core.config import settings

app = FastAPI(
    title="CookAI API",
    version="0.1.0",
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(jobs_router, prefix="/api")
app.include_router(recipes_router, prefix="/api")
