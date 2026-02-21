from fastapi import FastAPI
from app.api.routes import scan, auth

app = FastAPI(title="Version Checker API")

app.include_router(scan.router)
app.include_router(auth.router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

