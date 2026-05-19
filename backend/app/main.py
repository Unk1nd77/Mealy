from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes.auth import router as auth_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.plans import router as plans_router
from app.api.routes.recipes import router as recipes_router
from app.api.routes.users import router as users_router
from app.config import settings
from app.core import cache
from app.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Mealy backend starting")
    if settings.DEV_MODE:
        logger.warning(
            "⚠ DEV_MODE enabled — auth bypassed, CORS=*, register is idempotent. "
            "DO NOT use in production."
        )
        logger.warning(
            "DEV_MODE: requests without bearer token auto-login as {}",
            settings.DEV_USER_EMAIL,
        )
    yield
    await cache.close()
    logger.info("Mealy backend shutting down")


app = FastAPI(
    title="Mealy API",
    description="AI-powered personalized meal planning with verified KBJU",
    version="0.1.0",
    lifespan=lifespan,
)

_cors_origins = (
    ["*"]
    if settings.DEV_MODE
    else [
        "http://localhost:4321",
        "http://127.0.0.1:4321",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=not settings.DEV_MODE,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(plans_router)
app.include_router(recipes_router)
app.include_router(catalog_router)


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok"}
