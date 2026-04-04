import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import scan, auth, usage
from app.infrastructure.config import settings

logger = logging.getLogger(__name__)


app = FastAPI(title="Version Checker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router)
app.include_router(auth.router)
app.include_router(usage.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
