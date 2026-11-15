"""
ChimeraFlow API - FastAPI Backend
Main application entry point
"""
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
import logging

# Import configuration
from config import (
    NODE_ENV,
    PORT,
    LOG_LEVEL,
    CORS_ORIGINS,
)

# Import routers
from api.auth import require_auth, router as auth_router
from api.errors import validation_error_handler
from api.rate_limit import register_rate_limiting
from api.sources import router as sources_router
from api.rules import router as rules_router
from api.correlations import router as correlations_router

# Import database session
from models.base import SessionLocal
from models.seed import seed_predefined_rules

# Configure logging (root level untouched when LOG_LEVEL is not set)
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# CORS configuration (whitelist, entries trimmed, empty entries dropped)
cors_origins = [origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Seed predefined rules. Startup fails if seeding fails.

    The schema is not created here: `alembic upgrade head` runs before the
    server starts (container entrypoint).
    """
    logger.info(f"ChimeraFlow API starting in {NODE_ENV} mode")
    logger.info(f"CORS origins: {cors_origins}")

    try:
        with SessionLocal() as db:
            seed_predefined_rules(db)
    except Exception:
        logger.exception("Database initialization failed")
        raise
    logger.info("Database initialized successfully")
    yield


def docs_urls(node_env: Optional[str]) -> Dict[str, Any]:
    """FastAPI options of the interactive documentation for an environment.

    Swagger UI and ReDoc cannot send the Bearer header when they load the
    schema, so protecting them is not practical. In production they are not
    served at all: the API surface is not published to anonymous visitors.

    Args:
        node_env: Value of BACKEND_NODE_ENV.

    Returns:
        Keyword arguments for FastAPI (empty: documentation served at the defaults).
    """
    if node_env == "production":
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


DOCS_ENABLED = not docs_urls(NODE_ENV)

app = FastAPI(
    title="ChimeraFlow API",
    description="Correlation engine for Excel, Access, and WhatsApp data sources",
    version="0.1.0",
    lifespan=lifespan,
    **docs_urls(NODE_ENV),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Retry-After is not CORS-safelisted: without this the login page cannot read it
    expose_headers=["Retry-After"],
)

register_rate_limiting(app)
app.add_exception_handler(RequestValidationError, validation_error_handler)

# Include routers. Every /api/v1 router except auth requires a Bearer token: the
# dependency is attached here so that a new router cannot be forgotten by an
# endpoint author (login is public, /auth/me checks the token itself).
app.include_router(auth_router)
app.include_router(sources_router, dependencies=[Depends(require_auth)])
app.include_router(rules_router, dependencies=[Depends(require_auth)])
app.include_router(correlations_router, dependencies=[Depends(require_auth)])


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "chimeraflow-api",
        "version": "0.1.0",
        "environment": NODE_ENV
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "ChimeraFlow API",
        "docs": "/docs" if DOCS_ENABLED else None,
        "health": "/health",
        "endpoints": {
            "auth": "/api/v1/auth",
            "sources": "/api/v1/sources",
            "rules": "/api/v1/rules",
            "correlations": "/api/v1/correlations"
        }
    }


if __name__ == "__main__":
    import uvicorn

    # Let uvicorn use its own default port when BACKEND_PORT is not set
    uvicorn_options = {} if PORT is None else {"port": PORT}
    uvicorn.run(app, host="0.0.0.0", **uvicorn_options)
