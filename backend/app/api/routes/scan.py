from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.usecases.scanner import ScanRepositoryUseCase
from app.usecases.scan_jobs import ScanJobService, serialize_scan_job
from app.adapters.database_repo import (
    EolStatusRepository,
    OrgRepository,
    RepoRepository,
    ScanJobRepository,
)
from app.adapters.sqs_scan_queue import SqsScanQueue
from app.infrastructure.database import get_db_session
from app.api.auth_deps import verify_org_access
from app.domain.entities import User

router = APIRouter(prefix="/api/v1/scan", tags=["Scan"])


async def get_scan_usecase(
    session: AsyncSession = Depends(get_db_session),
) -> ScanRepositoryUseCase:
    repo_repository = RepoRepository(session)
    eol_status_repository = EolStatusRepository(session)
    return ScanRepositoryUseCase(repo_repository, eol_status_repository)


async def get_scan_job_service(
    session: AsyncSession = Depends(get_db_session),
) -> ScanJobService:
    org_repository = OrgRepository(session)
    repo_repository = RepoRepository(session)
    eol_status_repository = EolStatusRepository(session)
    scan_job_repository = ScanJobRepository(session)
    queue = SqsScanQueue()
    scan_usecase = ScanRepositoryUseCase(repo_repository, eol_status_repository)
    return ScanJobService(
        org_repository,
        repo_repository,
        eol_status_repository,
        scan_job_repository,
        queue,
        scanner_usecase=scan_usecase,
    )


@router.get("/orgs/{org_id}")
async def get_organization_scan_results(
    org_id: str,
    service: ScanJobService = Depends(get_scan_job_service),
    user: User = Depends(verify_org_access),
):
    """Get persisted scan results for an organization."""
    try:
        return await service.get_scan_results(
            org_id, user.github_access_token, user.username
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orgs/{org_id}/jobs/{job_id}")
async def get_scan_job(
    org_id: str,
    job_id: str,
    service: ScanJobService = Depends(get_scan_job_service),
    user: User = Depends(verify_org_access),
):
    """Get the current state of a scan job."""
    try:
        job = await service.get_job(org_id, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Scan job not found")
        return serialize_scan_job(job)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orgs/{org_id}", status_code=status.HTTP_202_ACCEPTED)
async def scan_organization_repos(
    org_id: str,
    service: ScanJobService = Depends(get_scan_job_service),
    user: User = Depends(verify_org_access),
):
    """Queue a new scan for an organization's repos."""
    try:
        job = await service.enqueue_scan(org_id, user.username)
        return serialize_scan_job(job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
