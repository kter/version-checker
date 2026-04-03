import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

import app.usecases.scan_jobs as scan_jobs_module
from app.domain.entities import (
    SCAN_JOB_STATUS_FAILED,
    SCAN_JOB_STATUS_PARTIAL_FAILED,
    EolStatus,
    Organization,
    Repository,
    ScanJob,
)
from app.usecases.scan_jobs import (
    SCAN_JOB_BOOTSTRAP_STALLED_ERROR_MESSAGE,
    SCAN_JOB_MESSAGE_BOOTSTRAP,
    SCAN_JOB_MESSAGE_REPOSITORY,
    SCAN_JOB_PROGRESS_STALLED_ERROR_MESSAGE,
    ScanJobService,
    ScanJobWorkerService,
    serialize_scan_job,
)


class TestScanJobService:
    @pytest.mark.asyncio
    async def test_get_scan_results_uses_cached_repository_listing(self):
        org_repository = AsyncMock()
        user_repository = AsyncMock()
        repo_repository = AsyncMock()
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        scan_job_repository.find_latest_by_org.return_value = None
        queue = AsyncMock()
        scanner_usecase = AsyncMock()
        scanner_usecase.list_repositories.return_value = [
            Repository(
                id="repo-1",
                github_id=1,
                name="app",
                full_name="octocat/app",
                org_id="octocat",
                owner_login="octocat",
                default_branch="main",
                is_selected=True,
            )
        ]
        scanner_usecase.get_saved_results.return_value = []

        service = ScanJobService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
            scanner_usecase=scanner_usecase,
        )

        result = await service.get_scan_results("octocat", "gho_test", "octocat")

        assert result["repository_count"] == 1
        scanner_usecase.list_repositories.assert_awaited_once_with(
            "octocat",
            "gho_test",
            "octocat",
            use_cache=True,
        )

    @pytest.mark.asyncio
    async def test_get_scan_results_includes_all_detected_items_and_eol_summary(self):
        org_repository = AsyncMock()
        user_repository = AsyncMock()
        repo_repository = AsyncMock()
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        scan_job_repository.find_latest_by_org.return_value = None
        queue = AsyncMock()
        scanner_usecase = AsyncMock()
        scanner_usecase.list_repositories.return_value = [
            Repository(
                id="repo-1",
                github_id=1,
                name="app",
                full_name="octocat/app",
                org_id="octocat",
                owner_login="octocat",
                default_branch="main",
                is_selected=True,
            )
        ]
        scanner_usecase.get_saved_results.return_value = [
            EolStatus(
                repo_id="repo-1",
                framework_name="Nuxt",
                current_version="3.16.0",
                is_eol=False,
                last_scanned_at=datetime(2026, 3, 29, 12, 0, 0),
                source_path="frontend/package.json",
            ),
            EolStatus(
                repo_id="repo-1",
                framework_name="Node.js",
                current_version="18.0.0",
                is_eol=True,
                eol_date=datetime(2025, 4, 30, 0, 0, 0),
                last_scanned_at=datetime(2026, 3, 28, 12, 0, 0),
                source_path="frontend/package.json",
            ),
        ]

        service = ScanJobService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
            scanner_usecase=scanner_usecase,
        )

        result = await service.get_scan_results("octocat", "gho_test", "octocat")

        repository = result["repositories"][0]
        assert repository["detected_item_count"] == 2
        assert repository["framework"] == "Node.js"
        assert repository["version"] == "18.0.0"
        assert repository["is_eol"] is True
        assert repository["source_path"] == "frontend/package.json"
        assert repository["detected_items"] == [
            {
                "name": "Node.js",
                "version": "18.0.0",
                "is_eol": True,
                "eol_date": "2025-04-30T00:00:00",
                "last_scanned_at": "2026-03-28T12:00:00+00:00",
                "source_path": "frontend/package.json",
            },
            {
                "name": "Nuxt",
                "version": "3.16.0",
                "is_eol": False,
                "eol_date": None,
                "last_scanned_at": "2026-03-29T12:00:00+00:00",
                "source_path": "frontend/package.json",
            },
        ]

    @pytest.mark.asyncio
    async def test_get_scan_results_allows_docker_items_to_drive_summary(self):
        org_repository = AsyncMock()
        user_repository = AsyncMock()
        repo_repository = AsyncMock()
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        scan_job_repository.find_latest_by_org.return_value = None
        queue = AsyncMock()
        scanner_usecase = AsyncMock()
        scanner_usecase.list_repositories.return_value = [
            Repository(
                id="repo-1",
                github_id=1,
                name="app",
                full_name="octocat/app",
                org_id="octocat",
                owner_login="octocat",
                default_branch="main",
                is_selected=True,
            )
        ]
        scanner_usecase.get_saved_results.return_value = [
            EolStatus(
                repo_id="repo-1",
                framework_name="Python",
                current_version="3.12",
                is_eol=False,
                last_scanned_at=datetime(2026, 3, 29, 12, 0, 0),
                source_path="backend/Dockerfile",
            ),
            EolStatus(
                repo_id="repo-1",
                framework_name="Debian",
                current_version="bookworm",
                is_eol=True,
                eol_date=datetime(2026, 6, 10, 0, 0, 0),
                last_scanned_at=datetime(2026, 3, 30, 12, 0, 0),
                source_path="backend/Dockerfile",
            ),
        ]

        service = ScanJobService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
            scanner_usecase=scanner_usecase,
        )

        result = await service.get_scan_results("octocat", "gho_test", "octocat")

        repository = result["repositories"][0]
        assert repository["framework"] == "Debian"
        assert repository["version"] == "bookworm"
        assert repository["is_eol"] is True
        assert repository["source_path"] == "backend/Dockerfile"
        assert repository["detected_items"][0]["name"] == "Debian"
        assert repository["detected_items"][0]["source_path"] == "backend/Dockerfile"

    @pytest.mark.asyncio
    async def test_enqueue_scan_reuses_active_job(self):
        active_job = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status="running",
        )

        org_repository = AsyncMock()
        user_repository = AsyncMock()
        repo_repository = AsyncMock()
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        scan_job_repository.find_active_by_org.return_value = active_job
        queue = AsyncMock()

        service = ScanJobService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
        )

        result = await service.enqueue_scan("octocat", "octocat")

        assert result == active_job
        queue.send_message.assert_not_awaited()

    def test_serialize_scan_job_uses_explicit_utc_offsets(self):
        serialized = serialize_scan_job(
            ScanJob(
                id="job-1",
                org_id="octocat",
                requested_by="octocat",
                status="running",
                created_at=datetime(2026, 4, 3, 9, 0, 0),
                updated_at=datetime(2026, 4, 3, 9, 5, 0, tzinfo=UTC),
                started_at=datetime(2026, 4, 3, 9, 1, 0),
                finished_at=datetime(2026, 4, 3, 9, 6, 0),
            )
        )

        assert serialized == {
            "job_id": "job-1",
            "org_id": "octocat",
            "status": "running",
            "total_repos": 0,
            "completed_repos": 0,
            "failed_repos": 0,
            "started_at": "2026-04-03T09:01:00+00:00",
            "finished_at": "2026-04-03T09:06:00+00:00",
            "error_message": None,
            "created_at": "2026-04-03T09:00:00+00:00",
            "updated_at": "2026-04-03T09:05:00+00:00",
        }

    @pytest.mark.asyncio
    async def test_enqueue_scan_replaces_stale_active_job(self, monkeypatch):
        now = datetime(2026, 4, 3, 11, 0, 0)
        monkeypatch.setattr(scan_jobs_module, "_utcnow_naive", lambda: now)

        stale_job = ScanJob(
            id="job-stale",
            org_id="octocat",
            requested_by="octocat",
            status="queued",
            created_at=datetime(2026, 4, 3, 10, 50, 0),
            updated_at=datetime(2026, 4, 3, 10, 50, 0),
        )
        refreshed_job = ScanJob(
            id="job-2",
            org_id="octocat",
            requested_by="octocat",
        )

        org_repository = AsyncMock()
        org_repository.find_by_login.return_value = Organization(
            id="octocat",
            github_id=1,
            name="octocat",
            login="octocat",
            github_access_token="gho_test",
        )
        user_repository = AsyncMock()
        repo_repository = AsyncMock()
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        scan_job_repository.find_active_by_org.return_value = stale_job
        scan_job_repository.finalize.return_value = ScanJob(
            id="job-stale",
            org_id="octocat",
            requested_by="octocat",
            status=SCAN_JOB_STATUS_FAILED,
            error_message=SCAN_JOB_BOOTSTRAP_STALLED_ERROR_MESSAGE,
            created_at=stale_job.created_at,
            updated_at=now,
            finished_at=now,
        )
        scan_job_repository.create.return_value = refreshed_job
        queue = AsyncMock()
        scanner_usecase = AsyncMock()
        scanner_usecase.list_repositories.return_value = [
            Repository(
                id="repo-1",
                github_id=1,
                name="app",
                full_name="octocat/app",
                org_id="octocat",
                owner_login="octocat",
                default_branch="main",
                is_selected=True,
            )
        ]

        service = ScanJobService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
            scanner_usecase=scanner_usecase,
        )

        result = await service.enqueue_scan("octocat", "octocat")

        assert result == refreshed_job
        scan_job_repository.finalize.assert_awaited_once_with(
            "job-stale",
            SCAN_JOB_STATUS_FAILED,
            SCAN_JOB_BOOTSTRAP_STALLED_ERROR_MESSAGE,
        )
        scan_job_repository.create.assert_awaited_once()
        queue.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_enqueue_scan_creates_bootstrap_job(self):
        org_repository = AsyncMock()
        user_repository = AsyncMock()
        org_repository.find_by_login.return_value = Organization(
            id="octocat",
            github_id=1,
            name="octocat",
            login="octocat",
            github_access_token="gho_test",
        )
        repo_repository = AsyncMock()
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        scan_job_repository.find_active_by_org.return_value = None
        scanner_usecase = AsyncMock()
        scanner_usecase.list_repositories.return_value = [
            Repository(
                id="repo-1",
                github_id=1,
                name="app",
                full_name="octocat/app",
                org_id="octocat",
                owner_login="octocat",
                default_branch="main",
                is_selected=True,
            )
        ]

        created_jobs = []

        async def create_job(job):
            created_jobs.append(job)
            return job

        scan_job_repository.create.side_effect = create_job
        queue = AsyncMock()

        service = ScanJobService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
            scanner_usecase=scanner_usecase,
        )

        job = await service.enqueue_scan("octocat", "octocat")

        assert job.org_id == "octocat"
        assert job.status == "queued"
        queue.send_message.assert_awaited_once_with(
            {
                "message_type": SCAN_JOB_MESSAGE_BOOTSTRAP,
                "job_id": job.id,
                "org_id": "octocat",
            }
        )
        assert created_jobs[0].requested_by == "octocat"
        scanner_usecase.list_repositories.assert_awaited_once_with(
            "octocat",
            "gho_test",
            "octocat",
            use_cache=True,
        )

    @pytest.mark.asyncio
    async def test_enqueue_scan_rejects_when_no_repository_is_selected(self):
        org_repository = AsyncMock()
        user_repository = AsyncMock()
        org_repository.find_by_login.return_value = Organization(
            id="octocat",
            github_id=1,
            name="octocat",
            login="octocat",
            github_access_token="gho_test",
        )
        repo_repository = AsyncMock()
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        scan_job_repository.find_active_by_org.return_value = None
        queue = AsyncMock()
        scanner_usecase = AsyncMock()
        scanner_usecase.list_repositories.return_value = [
            Repository(
                id="repo-1",
                github_id=1,
                name="app",
                full_name="octocat/app",
                org_id="octocat",
                owner_login="octocat",
                default_branch="main",
                is_selected=False,
            )
        ]

        service = ScanJobService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
            scanner_usecase=scanner_usecase,
        )

        with pytest.raises(ValueError, match="No repositories selected for scanning"):
            await service.enqueue_scan("octocat", "octocat")

        scan_job_repository.create.assert_not_awaited()
        queue.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_selection_replaces_selection_set(self):
        org_repository = AsyncMock()
        user_repository = AsyncMock()
        repo_repository = AsyncMock()
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        queue = AsyncMock()
        scanner_usecase = AsyncMock()
        scanner_usecase.list_repositories.return_value = [
            Repository(
                id="repo-1",
                github_id=1,
                name="app",
                full_name="octocat/app",
                org_id="octocat",
                owner_login="octocat",
                default_branch="main",
                is_selected=True,
            ),
            Repository(
                id="repo-2",
                github_id=2,
                name="worker",
                full_name="octocat/worker",
                org_id="octocat",
                owner_login="octocat",
                default_branch="main",
                is_selected=False,
            ),
        ]

        service = ScanJobService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
            scanner_usecase=scanner_usecase,
        )

        result = await service.update_selection(
            "octocat",
            "gho_test",
            "octocat",
            ["repo-2"],
        )

        scanner_usecase.list_repositories.assert_awaited_once_with(
            "octocat",
            "gho_test",
            "octocat",
            use_cache=True,
        )
        repo_repository.replace_selection.assert_awaited_once_with(
            "octocat", ["repo-2"]
        )
        assert result == {"selected_repository_count": 1}

    @pytest.mark.asyncio
    async def test_get_scan_results_finalizes_stale_queued_job(self, monkeypatch):
        now = datetime(2026, 4, 3, 11, 0, 0)
        monkeypatch.setattr(scan_jobs_module, "_utcnow_naive", lambda: now)

        org_repository = AsyncMock()
        user_repository = AsyncMock()
        repo_repository = AsyncMock()
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        stale_job = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status="queued",
            created_at=datetime(2026, 4, 3, 10, 50, 0),
            updated_at=datetime(2026, 4, 3, 10, 50, 0),
        )
        scan_job_repository.find_latest_by_org.return_value = stale_job
        scan_job_repository.finalize.return_value = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status=SCAN_JOB_STATUS_FAILED,
            error_message=SCAN_JOB_BOOTSTRAP_STALLED_ERROR_MESSAGE,
            created_at=stale_job.created_at,
            updated_at=now,
            finished_at=now,
        )
        queue = AsyncMock()
        scanner_usecase = AsyncMock()
        scanner_usecase.list_repositories.return_value = []
        scanner_usecase.get_saved_results.return_value = []

        service = ScanJobService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
            scanner_usecase=scanner_usecase,
        )

        result = await service.get_scan_results("octocat", "gho_test", "octocat")

        scan_job_repository.finalize.assert_awaited_once_with(
            "job-1",
            SCAN_JOB_STATUS_FAILED,
            SCAN_JOB_BOOTSTRAP_STALLED_ERROR_MESSAGE,
        )
        assert result["latest_job"]["status"] == SCAN_JOB_STATUS_FAILED
        assert (
            result["latest_job"]["error_message"]
            == SCAN_JOB_BOOTSTRAP_STALLED_ERROR_MESSAGE
        )

    @pytest.mark.asyncio
    async def test_get_job_finalizes_stale_running_bootstrap_job(self, monkeypatch):
        now = datetime(2026, 4, 3, 11, 0, 0)
        monkeypatch.setattr(scan_jobs_module, "_utcnow_naive", lambda: now)

        org_repository = AsyncMock()
        user_repository = AsyncMock()
        repo_repository = AsyncMock()
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        stale_job = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status="running",
            total_repos=0,
            created_at=datetime(2026, 4, 3, 10, 55, 0),
            started_at=datetime(2026, 4, 3, 10, 56, 0),
            updated_at=datetime(2026, 4, 3, 10, 56, 0),
        )
        scan_job_repository.find_by_id.return_value = stale_job
        scan_job_repository.finalize.return_value = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status=SCAN_JOB_STATUS_FAILED,
            total_repos=0,
            error_message=SCAN_JOB_BOOTSTRAP_STALLED_ERROR_MESSAGE,
            created_at=stale_job.created_at,
            started_at=stale_job.started_at,
            updated_at=now,
            finished_at=now,
        )
        queue = AsyncMock()

        service = ScanJobService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
        )

        result = await service.get_job("octocat", "job-1")

        scan_job_repository.finalize.assert_awaited_once_with(
            "job-1",
            SCAN_JOB_STATUS_FAILED,
            SCAN_JOB_BOOTSTRAP_STALLED_ERROR_MESSAGE,
        )
        assert result.status == SCAN_JOB_STATUS_FAILED
        assert result.error_message == SCAN_JOB_BOOTSTRAP_STALLED_ERROR_MESSAGE

    @pytest.mark.asyncio
    async def test_get_job_finalizes_stale_running_repository_progress_job(
        self, monkeypatch
    ):
        now = datetime(2026, 4, 3, 11, 20, 0)
        monkeypatch.setattr(scan_jobs_module, "_utcnow_naive", lambda: now)

        org_repository = AsyncMock()
        user_repository = AsyncMock()
        repo_repository = AsyncMock()
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        stale_job = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status="running",
            total_repos=2,
            completed_repos=0,
            failed_repos=0,
            created_at=datetime(2026, 4, 3, 10, 55, 0),
            started_at=datetime(2026, 4, 3, 10, 56, 0),
            updated_at=datetime(2026, 4, 3, 11, 0, 0),
        )
        scan_job_repository.find_by_id.return_value = stale_job
        scan_job_repository.finalize.return_value = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status=SCAN_JOB_STATUS_FAILED,
            total_repos=2,
            completed_repos=0,
            failed_repos=0,
            error_message=SCAN_JOB_PROGRESS_STALLED_ERROR_MESSAGE,
            created_at=stale_job.created_at,
            started_at=stale_job.started_at,
            updated_at=now,
            finished_at=now,
        )
        queue = AsyncMock()

        service = ScanJobService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
        )

        result = await service.get_job("octocat", "job-1")

        scan_job_repository.finalize.assert_awaited_once_with(
            "job-1",
            SCAN_JOB_STATUS_FAILED,
            SCAN_JOB_PROGRESS_STALLED_ERROR_MESSAGE,
        )
        assert result.status == SCAN_JOB_STATUS_FAILED
        assert result.error_message == SCAN_JOB_PROGRESS_STALLED_ERROR_MESSAGE


class TestScanJobWorkerService:
    @pytest.mark.asyncio
    async def test_bootstrap_completes_empty_job(self):
        job = ScanJob(id="job-1", org_id="octocat", requested_by="octocat")

        org_repository = AsyncMock()
        user_repository = AsyncMock()
        org_repository.find_by_login.return_value = Organization(
            id="octocat",
            github_id=1,
            name="octocat",
            login="octocat",
            github_access_token="gho_test",
        )
        repo_repository = AsyncMock()
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        scan_job_repository.find_by_id.return_value = job
        scan_job_repository.start.return_value = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status="running",
            total_repos=0,
        )
        queue = AsyncMock()
        scanner_usecase = AsyncMock()
        scanner_usecase.list_repositories.return_value = []

        worker = ScanJobWorkerService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
            scanner_usecase=scanner_usecase,
        )

        await worker.process_message(
            {
                "message_type": SCAN_JOB_MESSAGE_BOOTSTRAP,
                "job_id": "job-1",
                "org_id": "octocat",
            }
        )

        scan_job_repository.start.assert_awaited_once_with("job-1", 0)
        scan_job_repository.mark_completed.assert_awaited_once_with("job-1")
        queue.send_messages.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bootstrap_queues_only_selected_repositories(self):
        job = ScanJob(id="job-1", org_id="octocat", requested_by="octocat")

        org_repository = AsyncMock()
        user_repository = AsyncMock()
        org_repository.find_by_login.return_value = Organization(
            id="octocat",
            github_id=1,
            name="octocat",
            login="octocat",
            github_access_token="gho_test",
        )
        repo_repository = AsyncMock()
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        scan_job_repository.find_by_id.return_value = job
        scan_job_repository.start.return_value = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status="running",
            total_repos=1,
        )
        queue = AsyncMock()
        scanner_usecase = AsyncMock()
        scanner_usecase.list_repositories.return_value = [
            Repository(
                id="repo-1",
                github_id=1,
                name="app",
                full_name="octocat/app",
                org_id="octocat",
                owner_login="octocat",
                default_branch="main",
                is_selected=True,
            ),
            Repository(
                id="repo-2",
                github_id=2,
                name="worker",
                full_name="octocat/worker",
                org_id="octocat",
                owner_login="octocat",
                default_branch="main",
                is_selected=False,
            ),
        ]

        worker = ScanJobWorkerService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
            scanner_usecase=scanner_usecase,
        )

        await worker.process_message(
            {
                "message_type": SCAN_JOB_MESSAGE_BOOTSTRAP,
                "job_id": "job-1",
                "org_id": "octocat",
            }
        )

        scanner_usecase.list_repositories.assert_awaited_once_with(
            "octocat",
            "gho_test",
            "octocat",
            use_cache=True,
        )
        scan_job_repository.start.assert_awaited_once_with("job-1", 1)
        queue.send_messages.assert_awaited_once_with(
            [
                {
                    "message_type": SCAN_JOB_MESSAGE_REPOSITORY,
                    "job_id": "job-1",
                    "org_id": "octocat",
                    "repo_id": "repo-1",
                }
            ]
        )

    @pytest.mark.asyncio
    async def test_repository_scan_finalizes_partial_failure(self):
        initial_job = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status="running",
            total_repos=2,
            completed_repos=1,
            failed_repos=0,
        )
        updated_job = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status="running",
            total_repos=2,
            completed_repos=1,
            failed_repos=1,
            error_message="Repository scan failed for octocat/broken: boom",
        )

        org_repository = AsyncMock()
        user_repository = AsyncMock()
        org_repository.find_by_login.return_value = Organization(
            id="octocat",
            github_id=1,
            name="octocat",
            login="octocat",
            github_access_token="gho_test",
        )
        repo_repository = AsyncMock()
        repo_repository.find_by_id.return_value = Repository(
            id="repo-1",
            github_id=1,
            name="broken",
            full_name="octocat/broken",
            org_id="octocat",
            owner_login="octocat",
            default_branch="main",
        )
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        scan_job_repository.find_by_id.return_value = initial_job
        scan_job_repository.record_repo_failure.return_value = updated_job
        queue = AsyncMock()
        scanner = AsyncMock()
        scanner.scan_repo.side_effect = RuntimeError("boom")

        worker = ScanJobWorkerService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
            scanner=scanner,
        )

        await worker.process_message(
            {
                "message_type": SCAN_JOB_MESSAGE_REPOSITORY,
                "job_id": "job-1",
                "org_id": "octocat",
                "repo_id": "repo-1",
            }
        )

        scan_job_repository.finalize.assert_awaited_once()
        finalize_args = scan_job_repository.finalize.await_args.args
        assert finalize_args[0] == "job-1"
        assert finalize_args[1] == SCAN_JOB_STATUS_PARTIAL_FAILED

    @pytest.mark.asyncio
    async def test_repository_scan_finalizes_failed_when_all_repos_fail(self):
        initial_job = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status="running",
            total_repos=1,
            completed_repos=0,
            failed_repos=0,
        )
        updated_job = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status="running",
            total_repos=1,
            completed_repos=0,
            failed_repos=1,
            error_message="Repository not found: repo-1",
        )

        org_repository = AsyncMock()
        user_repository = AsyncMock()
        org_repository.find_by_login.return_value = Organization(
            id="octocat",
            github_id=1,
            name="octocat",
            login="octocat",
            github_access_token="gho_test",
        )
        repo_repository = AsyncMock()
        repo_repository.find_by_id.return_value = None
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        scan_job_repository.find_by_id.return_value = initial_job
        scan_job_repository.record_repo_failure.return_value = updated_job
        queue = AsyncMock()

        worker = ScanJobWorkerService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
        )

        await worker.process_message(
            {
                "message_type": SCAN_JOB_MESSAGE_REPOSITORY,
                "job_id": "job-1",
                "org_id": "octocat",
                "repo_id": "repo-1",
            }
        )

        scan_job_repository.finalize.assert_awaited_once()
        finalize_args = scan_job_repository.finalize.await_args.args
        assert finalize_args[0] == "job-1"
        assert finalize_args[1] == SCAN_JOB_STATUS_FAILED

    @pytest.mark.asyncio
    async def test_repository_scan_records_timeout_as_failure(self, monkeypatch):
        monkeypatch.setattr(
            scan_jobs_module,
            "SCAN_JOB_REPOSITORY_TIMEOUT_SECONDS",
            0.01,
        )
        initial_job = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status="running",
            total_repos=1,
            completed_repos=0,
            failed_repos=0,
        )
        updated_job = ScanJob(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status="running",
            total_repos=1,
            completed_repos=0,
            failed_repos=1,
            error_message=(
                "Repository scan timed out for octocat/app after 0.01 seconds"
            ),
        )

        org_repository = AsyncMock()
        user_repository = AsyncMock()
        org_repository.find_by_login.return_value = Organization(
            id="octocat",
            github_id=1,
            name="octocat",
            login="octocat",
            github_access_token="gho_test",
        )
        repo_repository = AsyncMock()
        repo_repository.find_by_id.return_value = Repository(
            id="repo-1",
            github_id=1,
            name="app",
            full_name="octocat/app",
            org_id="octocat",
            owner_login="octocat",
            default_branch="main",
        )
        eol_status_repository = AsyncMock()
        scan_job_repository = AsyncMock()
        scan_job_repository.find_by_id.return_value = initial_job
        scan_job_repository.record_repo_failure.return_value = updated_job
        queue = AsyncMock()
        scanner = AsyncMock()

        async def slow_scan_repo(*_args, **_kwargs):
            await asyncio.sleep(0.05)
            return []

        scanner.scan_repo.side_effect = slow_scan_repo

        worker = ScanJobWorkerService(
            org_repository,
            user_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
            scanner=scanner,
        )

        await worker.process_message(
            {
                "message_type": SCAN_JOB_MESSAGE_REPOSITORY,
                "job_id": "job-1",
                "org_id": "octocat",
                "repo_id": "repo-1",
            }
        )

        scan_job_repository.record_repo_failure.assert_awaited_once_with(
            "job-1",
            "Repository scan timed out for octocat/app after 0.01 seconds",
        )
        scan_job_repository.finalize.assert_awaited_once()
        finalize_args = scan_job_repository.finalize.await_args.args
        assert finalize_args[0] == "job-1"
        assert finalize_args[1] == SCAN_JOB_STATUS_FAILED
