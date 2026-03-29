"""Unit tests for the scanner usecase."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.entities import EolStatus, Repository
from app.usecases.scanner import FrameworkEolScanner, ScanRepositoryUseCase


class TestFrameworkEolScanner:
    def test_extract_package_json_dependencies(self):
        scanner = FrameworkEolScanner()
        content = """
        {
          "dependencies": {
            "nuxt": "^3.16.0",
            "react": "18.3.1"
          },
          "engines": {
            "node": ">=20.11.0"
          }
        }
        """

        results = scanner._extract_dependencies("package.json", content)

        assert ("Nuxt", "3.16.0", "package.json") in [
            (dependency.framework_name, version, source_path)
            for dependency, version, source_path in results
        ]
        assert ("React", "18.3.1", "package.json") in [
            (dependency.framework_name, version, source_path)
            for dependency, version, source_path in results
        ]
        assert ("Node.js", "20.11.0", "package.json") in [
            (dependency.framework_name, version, source_path)
            for dependency, version, source_path in results
        ]

    def test_extract_pyproject_dependencies(self):
        scanner = FrameworkEolScanner()
        content = """
        [project]
        dependencies = ["Django>=5.1,<5.2"]
        requires-python = ">=3.12"
        """

        results = scanner._extract_dependencies("pyproject.toml", content)

        assert ("Django", "5.1", "pyproject.toml") in [
            (dependency.framework_name, version, source_path)
            for dependency, version, source_path in results
        ]
        assert ("Python", "3.12", "pyproject.toml") in [
            (dependency.framework_name, version, source_path)
            for dependency, version, source_path in results
        ]

    def test_match_release_prefers_specific_cycle(self):
        scanner = FrameworkEolScanner()
        releases = [
            {"name": "3", "releaseDate": "2022-01-01", "isEol": False},
            {"name": "3.5", "releaseDate": "2024-09-03", "isEol": False},
            {"name": "3.4", "releaseDate": "2023-12-29", "isEol": True},
        ]

        release = scanner._match_release(releases, "3.5.31")

        assert release["name"] == "3.5"


class TestScanRepositoryUseCase:
    @pytest.mark.asyncio
    async def test_get_saved_results(self):
        repo_repository = AsyncMock()
        status_repository = AsyncMock()
        status_repository.find_by_org.return_value = [
            EolStatus(repo_id="repo-1", framework_name="Nuxt", current_version="3.0.0")
        ]

        usecase = ScanRepositoryUseCase(repo_repository, status_repository)
        results = await usecase.get_saved_results("test-org")

        assert len(results) == 1
        assert results[0].framework_name == "Nuxt"
        status_repository.find_by_org.assert_called_once_with("test-org")

    @pytest.mark.asyncio
    async def test_list_repositories_reuses_saved_repositories(self):
        saved_repo = Repository(
            id="repo-db-1",
            github_id=101,
            name="web",
            full_name="test-org/web",
            org_id="test-org",
            owner_login="test-org",
            default_branch="main",
        )

        repo_repository = AsyncMock()
        repo_repository.find_by_org.return_value = [saved_repo]
        status_repository = AsyncMock()

        usecase = ScanRepositoryUseCase(repo_repository, status_repository)
        results = await usecase.list_repositories("test-org", "gho_test", "octocat")

        assert results == [saved_repo]
        repo_repository.find_by_org.assert_awaited_once_with("test-org")
        repo_repository.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_list_repositories_uses_personal_scope_for_authenticated_user(self):
        discovered_repo = Repository(
            id="",
            github_id=101,
            name="dotfiles",
            full_name="octocat/dotfiles",
            org_id="octocat",
            owner_login="octocat",
            default_branch="main",
        )
        saved_repo = Repository(
            id="repo-db-1",
            github_id=101,
            name="dotfiles",
            full_name="octocat/dotfiles",
            org_id="octocat",
            owner_login="octocat",
            default_branch="main",
        )

        repo_repository = AsyncMock()
        repo_repository.find_by_org.return_value = []
        repo_repository.save.return_value = saved_repo
        status_repository = AsyncMock()

        usecase = ScanRepositoryUseCase(repo_repository, status_repository)

        with patch(
            "app.usecases.scanner.GitHubClient.list_user_repositories",
            new=AsyncMock(return_value=[discovered_repo]),
        ) as mock_list_user_repositories, patch(
            "app.usecases.scanner.GitHubClient.list_org_repositories",
            new=AsyncMock(),
        ) as mock_list_org_repositories:
            results = await usecase.list_repositories("octocat", "gho_test", "octocat")

        assert results == [saved_repo]
        mock_list_user_repositories.assert_awaited_once_with("octocat")
        mock_list_org_repositories.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_execute_scans_and_persists_statuses(self):
        discovered_repo = Repository(
            id="",
            github_id=101,
            name="web",
            full_name="test-org/web",
            org_id="test-org",
            owner_login="test-org",
            default_branch="main",
        )
        saved_repo = Repository(
            id="repo-db-1",
            github_id=101,
            name="web",
            full_name="test-org/web",
            org_id="test-org",
            owner_login="test-org",
            default_branch="main",
        )
        status = EolStatus(
            repo_id="repo-db-1",
            framework_name="Nuxt",
            current_version="3.16.0",
            is_eol=False,
            last_scanned_at=datetime.now(UTC).replace(tzinfo=None),
            source_path="apps/web/package.json",
        )

        repo_repository = AsyncMock()
        repo_repository.find_by_org.return_value = []
        repo_repository.save.return_value = saved_repo
        status_repository = AsyncMock()
        scanner = AsyncMock()
        scanner.scan_repo.return_value = [status]

        usecase = ScanRepositoryUseCase(
            repo_repository, status_repository, scanner=scanner
        )

        with patch(
            "app.usecases.scanner.GitHubClient.list_org_repositories",
            new=AsyncMock(return_value=[discovered_repo]),
        ):
            results = await usecase.execute("test-org", "gho_test", "octocat")

        assert results == [status]
        repo_repository.save.assert_awaited_once()
        scanner.scan_repo.assert_awaited_once_with(saved_repo, "gho_test")
        status_repository.replace_for_repo.assert_awaited_once_with(
            "repo-db-1", [status]
        )

    @pytest.mark.asyncio
    async def test_execute_skips_failed_repository_scans(self):
        discovered_repos = [
            Repository(
                id="",
                github_id=101,
                name="web",
                full_name="test-org/web",
                org_id="test-org",
                owner_login="test-org",
                default_branch="main",
            ),
            Repository(
                id="",
                github_id=102,
                name="broken",
                full_name="test-org/broken",
                org_id="test-org",
                owner_login="test-org",
                default_branch="main",
            ),
        ]
        saved_repos = [
            Repository(
                id="repo-db-1",
                github_id=101,
                name="web",
                full_name="test-org/web",
                org_id="test-org",
                owner_login="test-org",
                default_branch="main",
            ),
            Repository(
                id="repo-db-2",
                github_id=102,
                name="broken",
                full_name="test-org/broken",
                org_id="test-org",
                owner_login="test-org",
                default_branch="main",
            ),
        ]
        status = EolStatus(
            repo_id="repo-db-1",
            framework_name="Nuxt",
            current_version="3.16.0",
            is_eol=False,
            last_scanned_at=datetime.now(UTC).replace(tzinfo=None),
            source_path="apps/web/package.json",
        )

        repo_repository = AsyncMock()
        repo_repository.find_by_org.return_value = []
        repo_repository.save.side_effect = saved_repos
        status_repository = AsyncMock()
        scanner = AsyncMock()
        scanner.scan_repo.side_effect = [[status], RuntimeError("boom")]

        usecase = ScanRepositoryUseCase(
            repo_repository, status_repository, scanner=scanner
        )

        with patch(
            "app.usecases.scanner.GitHubClient.list_org_repositories",
            new=AsyncMock(return_value=discovered_repos),
        ):
            results = await usecase.execute("test-org", "gho_test", "octocat")

        assert results == [status]
        assert scanner.scan_repo.await_count == 2
        status_repository.replace_for_repo.assert_awaited_once_with(
            "repo-db-1", [status]
        )
