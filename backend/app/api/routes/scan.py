from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.usecases.scanner import ScanRepositoryUseCase
from app.domain.entities import EolStatus

# Mock dependency injection
# In a real app we'd construct these from SQLAlchemy sessions and botocore sessions
async def get_scan_usecase() -> ScanRepositoryUseCase:
    # return ScanRepositoryUseCase(...)
    raise NotImplementedError("Dependency Injection not yet wired")

router = APIRouter(prefix="/api/v1/scan", tags=["Scan"])

@router.post("/orgs/{org_id}")
async def scan_organization_repos(
    org_id: str,
    usecase: ScanRepositoryUseCase = Depends(get_scan_usecase)
):
    try:
        statuses = await usecase.execute(org_id)
        # Convert entities to dict. Pydantic is better here for responses.
        return {"statuses": [
            {
                "repo_id": s.repo_id,
                "framework": s.framework_name,
                "version": s.current_version,
                "is_eol": s.is_eol,
                "eol_date": s.eol_date.isoformat() if s.eol_date else None,
                "last_scanned_at": s.last_scanned_at.isoformat()
            } for s in statuses
        ]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
