import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import scan, auth
from app.infrastructure.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup: initialize DB schema
    try:
        from app.infrastructure.init_db import init_db

        await init_db()
        logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.warning(
            f"Database initialization failed (will retry on first request): {e}"
        )
    yield
    # Shutdown: cleanup if needed


app = FastAPI(title="Version Checker API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router)
app.include_router(auth.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
