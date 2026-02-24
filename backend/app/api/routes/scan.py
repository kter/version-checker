from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.usecases.scanner import ScanRepositoryUseCase
from app.adapters.database_repo import RepoRepository
from app.adapters.dynamo_repo import DynamoEolCacheRepository
from app.infrastructure.database import get_db_session
from app.api.auth_deps import verify_org_access
from app.domain.entities import User

router = APIRouter(prefix="/api/v1/scan", tags=["Scan"])


async def get_scan_usecase(
    session: AsyncSession = Depends(get_db_session),
) -> ScanRepositoryUseCase:
    repo_repository = RepoRepository(session)
    cache_repository = DynamoEolCacheRepository()
    return ScanRepositoryUseCase(repo_repository, cache_repository)


@router.get("/orgs/{org_id}")
async def get_organization_scan_results(
    org_id: str,
    usecase: ScanRepositoryUseCase = Depends(get_scan_usecase),
    user: User = Depends(verify_org_access),
):
    """Get cached scan results for an organization."""
    try:
        statuses = await usecase.execute(org_id)
        return {
            "statuses": [
                {
                    "repo_id": s.repo_id,
                    "framework": s.framework_name,
                    "version": s.current_version,
                    "is_eol": s.is_eol,
                    "eol_date": s.eol_date.isoformat() if s.eol_date else None,
                    "last_scanned_at": s.last_scanned_at.isoformat(),
                }
                for s in statuses
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orgs/{org_id}")
async def scan_organization_repos(
    org_id: str,
    usecase: ScanRepositoryUseCase = Depends(get_scan_usecase),
    user: User = Depends(verify_org_access),
):
    """Trigger a new scan for an organization's repos."""
    try:
        statuses = await usecase.execute(org_id)
        return {
            "statuses": [
                {
                    "repo_id": s.repo_id,
                    "framework": s.framework_name,
                    "version": s.current_version,
                    "is_eol": s.is_eol,
                    "eol_date": s.eol_date.isoformat() if s.eol_date else None,
                    "last_scanned_at": s.last_scanned_at.isoformat(),
                }
                for s in statuses
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
