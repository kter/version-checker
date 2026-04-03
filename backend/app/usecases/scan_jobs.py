import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.domain.entities import (
    ACTIVE_SCAN_JOB_STATUSES,
    SCAN_JOB_STATUS_COMPLETED,
    SCAN_JOB_STATUS_FAILED,
    SCAN_JOB_STATUS_PARTIAL_FAILED,
    Organization,
    ScanJob,
)
from app.domain.interfaces import (
    IEolStatusRepository,
    IOrgRepository,
    IRepoRepository,
    IScanJobRepository,
    IUserRepository,
)
from app.usecases.github_auth import (
    GITHUB_REAUTH_REQUIRED_DETAIL,
    GitHubAuthorizationExpiredError,
    GitHubTokenService,
)
from app.usecases.scanner import FrameworkEolScanner, ScanRepositoryUseCase

logger = logging.getLogger(__name__)

SCAN_JOB_MESSAGE_BOOTSTRAP = "bootstrap_job"
SCAN_JOB_MESSAGE_REPOSITORY = "scan_repository"


class ScanJobService:
    def __init__(
        self,
        org_repository: IOrgRepository,
        user_repository: IUserRepository,
        repo_repository: IRepoRepository,
        eol_status_repository: IEolStatusRepository,
        scan_job_repository: IScanJobRepository,
        queue,
        scanner_usecase: Optional[ScanRepositoryUseCase] = None,
        token_service: Optional[GitHubTokenService] = None,
    ):
        self.org_repository = org_repository
        self.user_repository = user_repository
        self.repo_repository = repo_repository
        self.eol_status_repository = eol_status_repository
        self.scan_job_repository = scan_job_repository
        self.queue = queue
        self.token_service = token_service or GitHubTokenService()
        self.scanner_usecase = scanner_usecase or ScanRepositoryUseCase(
            repo_repository,
            eol_status_repository,
        )

    async def get_scan_results(
        self, org_id: str, github_access_token: str, user_login: str
    ) -> Dict[str, Any]:
        repos = await self.scanner_usecase.list_repositories(
            org_id,
            github_access_token,
            user_login,
            use_cache=True,
        )
        statuses = await self.scanner_usecase.get_saved_results(org_id)
        latest_job = await self.scan_job_repository.find_latest_by_org(org_id)
        statuses_by_repo = _group_statuses_by_repo(
            statuses, {repo.id for repo in repos}
        )
        return {
            "repository_count": len(repos),
            "selected_repository_count": len(
                [repo for repo in repos if repo.is_selected]
            ),
            "repositories": [
                _serialize_repository(repo, statuses_by_repo.get(repo.id, []))
                for repo in repos
            ],
            "latest_job": serialize_scan_job(latest_job),
        }

    async def enqueue_scan(self, org_id: str, requested_by: str) -> ScanJob:
        active_job = await self.scan_job_repository.find_active_by_org(org_id)
        if active_job:
            return active_job

        organization = await self.org_repository.find_by_login(org_id)
        repositories = await self._list_repositories_for_organization(
            organization,
            org_id,
            requested_by,
        )
        if not any(repo.is_selected for repo in repositories):
            raise ValueError("No repositories selected for scanning")

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

    async def update_selection(
        self,
        org_id: str,
        github_access_token: str,
        user_login: str,
        selected_repo_ids: List[str],
    ) -> Dict[str, Any]:
        normalized_selected_repo_ids = sorted(set(selected_repo_ids))
        repositories = await self.scanner_usecase.list_repositories(
            org_id,
            github_access_token,
            user_login,
        )
        current_repo_ids = {repo.id for repo in repositories}
        unknown_repo_ids = sorted(set(normalized_selected_repo_ids) - current_repo_ids)
        if unknown_repo_ids:
            raise ValueError(
                f"Unknown repositories in selection: {', '.join(unknown_repo_ids)}"
            )

        await self.repo_repository.replace_selection(
            org_id, normalized_selected_repo_ids
        )
        return {
            "selected_repository_count": len(normalized_selected_repo_ids),
        }

    async def _list_repositories_for_organization(
        self,
        organization: Optional[Organization],
        org_id: str,
        user_login: str,
    ) -> List:
        if not organization:
            raise ValueError("No GitHub token is available for this account")
        access_token = await self._get_organization_access_token(organization)
        try:
            return await self.scanner_usecase.list_repositories(
                org_id,
                access_token,
                user_login,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 401:
                raise
        refreshed_token = await self._get_organization_access_token(
            organization,
            force_refresh=True,
        )
        return await self.scanner_usecase.list_repositories(
            org_id,
            refreshed_token,
            user_login,
        )

    async def _get_organization_access_token(
        self,
        organization: Organization,
        *,
        force_refresh: bool = False,
    ) -> str:
        if organization.token_owner_user_id:
            user = await self.user_repository.find_by_id(
                organization.token_owner_user_id
            )
            if user:
                user = await self.token_service.ensure_user_access_token(
                    self.user_repository,
                    user,
                    force_refresh=force_refresh,
                )
                if user.github_access_token:
                    if organization.github_access_token != user.github_access_token:
                        organization.github_access_token = user.github_access_token
                        await self.org_repository.save(organization)
                    return user.github_access_token

        if organization.github_access_token and not force_refresh:
            return organization.github_access_token

        raise GitHubAuthorizationExpiredError(GITHUB_REAUTH_REQUIRED_DETAIL)


class ScanJobWorkerService:
    def __init__(
        self,
        org_repository: IOrgRepository,
        user_repository: IUserRepository,
        repo_repository: IRepoRepository,
        eol_status_repository: IEolStatusRepository,
        scan_job_repository: IScanJobRepository,
        queue,
        scanner_usecase: Optional[ScanRepositoryUseCase] = None,
        scanner: Optional[FrameworkEolScanner] = None,
        token_service: Optional[GitHubTokenService] = None,
    ):
        self.org_repository = org_repository
        self.user_repository = user_repository
        self.repo_repository = repo_repository
        self.eol_status_repository = eol_status_repository
        self.scan_job_repository = scan_job_repository
        self.queue = queue
        self.token_service = token_service or GitHubTokenService()
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
        if not organization:
            await self.scan_job_repository.finalize(
                job_id,
                SCAN_JOB_STATUS_FAILED,
                GITHUB_REAUTH_REQUIRED_DETAIL,
            )
            return

        try:
            repos = await self._list_repositories_for_organization(
                organization,
                org_id,
                job.requested_by,
            )
        except GitHubAuthorizationExpiredError:
            await self.scan_job_repository.finalize(
                job_id,
                SCAN_JOB_STATUS_FAILED,
                GITHUB_REAUTH_REQUIRED_DETAIL,
            )
            return
        selected_repos = [repo for repo in repos if repo.is_selected]
        await self.scan_job_repository.start(job_id, len(selected_repos))

        if not selected_repos:
            await self.scan_job_repository.mark_completed(job_id)
            return

        repo_messages = [
            {
                "message_type": SCAN_JOB_MESSAGE_REPOSITORY,
                "job_id": job_id,
                "org_id": org_id,
                "repo_id": repo.id,
            }
            for repo in selected_repos
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
        if not organization:
            updated_job = await self.scan_job_repository.record_repo_failure(
                job_id,
                GITHUB_REAUTH_REQUIRED_DETAIL,
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
            access_token = await self._get_organization_access_token(organization)
            statuses = await self._scan_repository_with_retry(
                organization,
                repository,
                access_token,
            )
            await self.eol_status_repository.replace_for_repo(repository.id, statuses)
            updated_job = await self.scan_job_repository.record_repo_success(job_id)
        except GitHubAuthorizationExpiredError:
            updated_job = await self.scan_job_repository.record_repo_failure(
                job_id,
                GITHUB_REAUTH_REQUIRED_DETAIL,
            )
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

    async def _list_repositories_for_organization(
        self,
        organization: Optional[Organization],
        org_id: str,
        user_login: str,
    ) -> List:
        if not organization:
            raise ValueError("No GitHub token is available for this account")
        access_token = await self._get_organization_access_token(organization)
        try:
            return await self.scanner_usecase.list_repositories(
                org_id,
                access_token,
                user_login,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 401:
                raise
        refreshed_token = await self._get_organization_access_token(
            organization,
            force_refresh=True,
        )
        return await self.scanner_usecase.list_repositories(
            org_id,
            refreshed_token,
            user_login,
        )

    async def _scan_repository_with_retry(
        self,
        organization: Organization,
        repository,
        access_token: str,
    ) -> List:
        try:
            return await self.scanner.scan_repo(repository, access_token)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 401:
                raise
        refreshed_token = await self._get_organization_access_token(
            organization,
            force_refresh=True,
        )
        return await self.scanner.scan_repo(repository, refreshed_token)

    async def _get_organization_access_token(
        self,
        organization: Organization,
        *,
        force_refresh: bool = False,
    ) -> str:
        if organization.token_owner_user_id:
            user = await self.user_repository.find_by_id(
                organization.token_owner_user_id
            )
            if user:
                user = await self.token_service.ensure_user_access_token(
                    self.user_repository,
                    user,
                    force_refresh=force_refresh,
                )
                if user.github_access_token:
                    if organization.github_access_token != user.github_access_token:
                        organization.github_access_token = user.github_access_token
                        await self.org_repository.save(organization)
                    return user.github_access_token

        if organization.github_access_token and not force_refresh:
            return organization.github_access_token

        raise GitHubAuthorizationExpiredError(GITHUB_REAUTH_REQUIRED_DETAIL)


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


def _group_statuses_by_repo(
    statuses, active_repo_ids: set[str]
) -> Dict[str, List[Any]]:
    grouped: Dict[str, List[Any]] = {}
    for status in statuses:
        if status.repo_id not in active_repo_ids:
            continue
        grouped.setdefault(status.repo_id, []).append(status)
    return grouped


def _sort_statuses(statuses: List[Any]) -> List[Any]:
    return sorted(
        statuses,
        key=lambda status: (
            status.is_eol,
            status.last_scanned_at or datetime.min,
            status.framework_name,
        ),
        reverse=True,
    )


def _serialize_detection_item(status: Any) -> Dict[str, Any]:
    return {
        "name": status.framework_name,
        "version": status.current_version,
        "is_eol": status.is_eol,
        "eol_date": status.eol_date.isoformat() if status.eol_date else None,
        "last_scanned_at": (
            status.last_scanned_at.isoformat() if status.last_scanned_at else None
        ),
        "source_path": status.source_path,
    }


def _serialize_repository(repo, statuses) -> Dict[str, Any]:
    sorted_statuses = _sort_statuses(statuses)
    primary_status = sorted_statuses[0] if sorted_statuses else None
    has_eol_status = any(status.is_eol for status in sorted_statuses)
    return {
        "repository_id": repo.id,
        "repo_id": repo.full_name,
        "is_selected": repo.is_selected,
        "detected_item_count": len(sorted_statuses),
        "detected_items": [
            _serialize_detection_item(status) for status in sorted_statuses
        ],
        "framework": primary_status.framework_name if primary_status else None,
        "version": primary_status.current_version if primary_status else None,
        "is_eol": has_eol_status if primary_status else None,
        "eol_date": (
            primary_status.eol_date.isoformat()
            if primary_status and primary_status.eol_date
            else None
        ),
        "last_scanned_at": (
            primary_status.last_scanned_at.isoformat() if primary_status else None
        ),
        "source_path": primary_status.source_path if primary_status else None,
    }
