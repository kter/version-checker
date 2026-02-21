from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import scan, auth

app = FastAPI(title="Version Checker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router)
app.include_router(auth.router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

