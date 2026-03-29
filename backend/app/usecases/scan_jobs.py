import logging
import uuid
from typing import Any, Dict, Optional

from app.domain.entities import (
    ACTIVE_SCAN_JOB_STATUSES,
    SCAN_JOB_STATUS_COMPLETED,
    SCAN_JOB_STATUS_FAILED,
    SCAN_JOB_STATUS_PARTIAL_FAILED,
    ScanJob,
)
from app.domain.interfaces import (
    IEolStatusRepository,
    IOrgRepository,
    IRepoRepository,
    IScanJobRepository,
)
from app.usecases.scanner import FrameworkEolScanner, ScanRepositoryUseCase

logger = logging.getLogger(__name__)

SCAN_JOB_MESSAGE_BOOTSTRAP = "bootstrap_job"
SCAN_JOB_MESSAGE_REPOSITORY = "scan_repository"


class ScanJobService:
    def __init__(
        self,
        org_repository: IOrgRepository,
        repo_repository: IRepoRepository,
        eol_status_repository: IEolStatusRepository,
        scan_job_repository: IScanJobRepository,
        queue,
        scanner_usecase: Optional[ScanRepositoryUseCase] = None,
    ):
        self.org_repository = org_repository
        self.repo_repository = repo_repository
        self.eol_status_repository = eol_status_repository
        self.scan_job_repository = scan_job_repository
        self.queue = queue
        self.scanner_usecase = scanner_usecase or ScanRepositoryUseCase(
            repo_repository,
            eol_status_repository,
        )

    async def get_scan_results(
        self, org_id: str, github_access_token: str, user_login: str
    ) -> Dict[str, Any]:
        await self.scanner_usecase.list_repositories(
            org_id, github_access_token, user_login
        )
        statuses = await self.scanner_usecase.get_saved_results(org_id)
        latest_job = await self.scan_job_repository.find_latest_by_org(org_id)
        repos = await self.repo_repository.find_by_org(org_id)
        repo_name_by_id = {repo.id: repo.full_name for repo in repos}
        return {
            "repository_count": len(repos),
            "statuses": [
                {
                    "repo_id": repo_name_by_id.get(status.repo_id, status.repo_id),
                    "framework": status.framework_name,
                    "version": status.current_version,
                    "is_eol": status.is_eol,
                    "eol_date": (
                        status.eol_date.isoformat() if status.eol_date else None
                    ),
                    "last_scanned_at": status.last_scanned_at.isoformat(),
                    "source_path": status.source_path,
                }
                for status in statuses
            ],
            "latest_job": serialize_scan_job(latest_job),
        }

    async def enqueue_scan(self, org_id: str, requested_by: str) -> ScanJob:
        active_job = await self.scan_job_repository.find_active_by_org(org_id)
        if active_job:
            return active_job

        organization = await self.org_repository.find_by_login(org_id)
        if not organization or not organization.github_access_token:
            raise ValueError("No GitHub token is available for this account")

        job = ScanJob(
            id=str(uuid.uuid4()),
            org_id=org_id,
            requested_by=requested_by,
        )
        created_job = await self.scan_job_repository.create(job)

        try:
            await self.queue.send_message(
                {
                    "message_type": SCAN_JOB_MESSAGE_BOOTSTRAP,
                    "job_id": created_job.id,
                    "org_id": created_job.org_id,
                }
            )
        except Exception:
            logger.exception("Failed to enqueue scan bootstrap for %s", org_id)
            await self.scan_job_repository.finalize(
                created_job.id,
                SCAN_JOB_STATUS_FAILED,
                "Failed to enqueue scan bootstrap job",
            )
            raise

        return created_job

    async def get_job(self, org_id: str, job_id: str) -> Optional[ScanJob]:
        job = await self.scan_job_repository.find_by_id(job_id)
        if not job or job.org_id != org_id:
            return None
        return job


class ScanJobWorkerService:
    def __init__(
        self,
        org_repository: IOrgRepository,
        repo_repository: IRepoRepository,
        eol_status_repository: IEolStatusRepository,
        scan_job_repository: IScanJobRepository,
        queue,
        scanner_usecase: Optional[ScanRepositoryUseCase] = None,
        scanner: Optional[FrameworkEolScanner] = None,
    ):
        self.org_repository = org_repository
        self.repo_repository = repo_repository
        self.eol_status_repository = eol_status_repository
        self.scan_job_repository = scan_job_repository
        self.queue = queue
        self.scanner_usecase = scanner_usecase or ScanRepositoryUseCase(
            repo_repository,
            eol_status_repository,
        )
        self.scanner = scanner or self.scanner_usecase.scanner

    async def process_message(self, payload: Dict[str, Any]) -> None:
        message_type = payload.get("message_type")
        if message_type == SCAN_JOB_MESSAGE_BOOTSTRAP:
            await self._process_bootstrap_job(payload["job_id"], payload["org_id"])
            return
        if message_type == SCAN_JOB_MESSAGE_REPOSITORY:
            await self._process_repository_scan(
                payload["job_id"], payload["org_id"], payload["repo_id"]
            )
            return
        raise ValueError(f"Unsupported scan job message type: {message_type}")

    async def _process_bootstrap_job(self, job_id: str, org_id: str) -> None:
        job = await self.scan_job_repository.find_by_id(job_id)
        if not job or job.status not in ACTIVE_SCAN_JOB_STATUSES:
            return

        organization = await self.org_repository.find_by_login(org_id)
        if not organization or not organization.github_access_token:
            await self.scan_job_repository.finalize(
                job_id,
                SCAN_JOB_STATUS_FAILED,
                "No GitHub token is available for this account",
            )
            return

        repos = await self.scanner_usecase.list_repositories(
            org_id, organization.github_access_token, job.requested_by
        )
        await self.scan_job_repository.start(job_id, len(repos))

        if not repos:
            await self.scan_job_repository.mark_completed(job_id)
            return

        repo_messages = [
            {
                "message_type": SCAN_JOB_MESSAGE_REPOSITORY,
                "job_id": job_id,
                "org_id": org_id,
                "repo_id": repo.id,
            }
            for repo in repos
        ]

        try:
            await self.queue.send_messages(repo_messages)
        except Exception as exc:
            logger.exception(
                "Failed to enqueue repository scan messages for %s", org_id
            )
            await self.scan_job_repository.finalize(
                job_id,
                SCAN_JOB_STATUS_FAILED,
                f"Failed to enqueue repository scan messages: {exc}",
            )

    async def _process_repository_scan(
        self, job_id: str, org_id: str, repo_id: str
    ) -> None:
        job = await self.scan_job_repository.find_by_id(job_id)
        if not job or job.status not in ACTIVE_SCAN_JOB_STATUSES:
            return

        organization = await self.org_repository.find_by_login(org_id)
        if not organization or not organization.github_access_token:
            updated_job = await self.scan_job_repository.record_repo_failure(
                job_id, "No GitHub token is available for this account"
            )
            await self._finalize_if_ready(updated_job)
            return

        repository = await self.repo_repository.find_by_id(repo_id)
        if not repository:
            updated_job = await self.scan_job_repository.record_repo_failure(
                job_id, f"Repository not found: {repo_id}"
            )
            await self._finalize_if_ready(updated_job)
            return

        try:
            statuses = await self.scanner.scan_repo(
                repository, organization.github_access_token
            )
            await self.eol_status_repository.replace_for_repo(repository.id, statuses)
            updated_job = await self.scan_job_repository.record_repo_success(job_id)
        except Exception as exc:
            logger.exception("Failed to scan repository %s", repository.full_name)
            updated_job = await self.scan_job_repository.record_repo_failure(
                job_id,
                f"Repository scan failed for {repository.full_name}: {exc}",
            )

        await self._finalize_if_ready(updated_job)

    async def _finalize_if_ready(self, job: Optional[ScanJob]) -> None:
        if not job:
            return
        if job.total_repos == 0:
            return
        if job.completed_repos + job.failed_repos < job.total_repos:
            return

        if job.failed_repos == 0:
            await self.scan_job_repository.finalize(job.id, SCAN_JOB_STATUS_COMPLETED)
            return

        error_message = _build_failure_summary(job)
        if job.completed_repos == 0:
            await self.scan_job_repository.finalize(
                job.id,
                SCAN_JOB_STATUS_FAILED,
                error_message,
            )
            return

        await self.scan_job_repository.finalize(
            job.id,
            SCAN_JOB_STATUS_PARTIAL_FAILED,
            error_message,
        )


def serialize_scan_job(job: Optional[ScanJob]) -> Optional[Dict[str, Any]]:
    if not job:
        return None
    return {
        "job_id": job.id,
        "org_id": job.org_id,
        "status": job.status,
        "total_repos": job.total_repos,
        "completed_repos": job.completed_repos,
        "failed_repos": job.failed_repos,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


def _build_failure_summary(job: ScanJob) -> str:
    summary = (
        f"{job.failed_repos} of {job.total_repos} repositories failed during scan."
    )
    if job.error_message:
        return f"{summary} Last error: {job.error_message}"
    return summary
