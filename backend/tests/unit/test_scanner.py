"""Unit tests for the scanner usecase."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from app.usecases.scanner import ScanRepositoryUseCase, FrameworkEolScanner
from app.domain.entities import Repository, EolStatus


class TestFrameworkEolScanner:
    @pytest.mark.asyncio
    async def test_scan_repo_returns_eol_status(self):
        scanner = FrameworkEolScanner()
        repo = Repository(
            id="r1", github_id=1, name="test-repo", full_name="org/test-repo"
        )
        results = await scanner.scan_repo(repo)

        assert len(results) == 1
        assert results[0].repo_id == "r1"
        assert results[0].framework_name == "nuxt"
        assert results[0].current_version == "2.15.8"
        assert results[0].is_eol is True
        assert results[0].eol_date == datetime(2023, 12, 31)

    @pytest.mark.asyncio
    async def test_scan_repo_returns_eol_status_entity(self):
        scanner = FrameworkEolScanner()
        repo = Repository(
            id="r2", github_id=2, name="other-repo", full_name="org/other-repo"
        )
        results = await scanner.scan_repo(repo)

        assert len(results) == 1
        assert isinstance(results[0], EolStatus)
        assert isinstance(results[0].last_scanned_at, datetime)


class TestScanRepositoryUseCase:
    @pytest.mark.asyncio
    async def test_execute_with_no_repos(self):
        repo_repo = AsyncMock()
        repo_repo.find_by_org.return_value = []
        cache_repo = AsyncMock()

        usecase = ScanRepositoryUseCase(repo_repo, cache_repo)
        results = await usecase.execute("org-empty")

        assert results == []
        repo_repo.find_by_org.assert_called_once_with("org-empty")
        cache_repo.get_eol_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_returns_cached_results(self):
        repo = Repository(id="r1", github_id=1, name="repo", full_name="org/repo")
        cached_status = EolStatus(
            repo_id="r1",
            framework_name="nuxt",
            current_version="3.0.0",
            is_eol=False,
        )

        repo_repo = AsyncMock()
        repo_repo.find_by_org.return_value = [repo]
        cache_repo = AsyncMock()
        cache_repo.get_eol_status.return_value = [cached_status]

        usecase = ScanRepositoryUseCase(repo_repo, cache_repo)
        results = await usecase.execute("org-1")

        assert len(results) == 1
        assert results[0].framework_name == "nuxt"
        assert results[0].is_eol is False
        cache_repo.set_eol_status.assert_not_called()  # No cache write on hit

    @pytest.mark.asyncio
    async def test_execute_scans_on_cache_miss(self):
        repo = Repository(id="r1", github_id=1, name="repo", full_name="org/repo")

        repo_repo = AsyncMock()
        repo_repo.find_by_org.return_value = [repo]
        cache_repo = AsyncMock()
        cache_repo.get_eol_status.return_value = []  # Cache miss

        usecase = ScanRepositoryUseCase(repo_repo, cache_repo)
        results = await usecase.execute("org-1")

        assert len(results) == 1
        assert results[0].is_eol is True  # Scanner mock returns EOL
        cache_repo.set_eol_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_multiple_repos(self):
        repos = [
            Repository(
                id=f"r{i}", github_id=i, name=f"repo-{i}", full_name=f"org/repo-{i}"
            )
            for i in range(3)
        ]

        repo_repo = AsyncMock()
        repo_repo.find_by_org.return_value = repos
        cache_repo = AsyncMock()
        cache_repo.get_eol_status.return_value = []  # All cache misses

        usecase = ScanRepositoryUseCase(repo_repo, cache_repo)
        results = await usecase.execute("org-1")

        assert len(results) == 3
        assert cache_repo.set_eol_status.call_count == 3
