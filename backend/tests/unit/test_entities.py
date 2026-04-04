"""Unit tests for domain entities."""

from datetime import datetime

from app.domain.entities import (
    EolStatus,
    Organization,
    Repository,
    ScanJob,
    ScanJobRepoProgress,
    TokenUsageEvent,
    User,
)


class TestUser:
    def test_create_user_with_defaults(self):
        user = User(id="u1", github_id=1, username="alice")
        assert user.id == "u1"
        assert user.github_id == 1
        assert user.username == "alice"
        assert user.email is None
        assert user.role == "member"
        assert user.organizations == []

    def test_create_user_with_all_fields(self):
        org = Organization(
            id="o1",
            github_id=100,
            name="Org",
            login="org",
            token_owner_user_id="u2",
        )
        user = User(
            id="u2",
            github_id=2,
            username="bob",
            email="bob@example.com",
            role="admin",
            organizations=[org],
            github_access_token="ghu_test",
            github_refresh_token="ghr_test",
        )
        assert user.email == "bob@example.com"
        assert user.role == "admin"
        assert len(user.organizations) == 1
        assert user.organizations[0].login == "org"
        assert user.github_access_token == "ghu_test"
        assert user.github_refresh_token == "ghr_test"


class TestOrganization:
    def test_create_organization(self):
        org = Organization(
            id="o1",
            github_id=100,
            name="Test Org",
            login="testorg",
            token_owner_user_id="u1",
        )
        assert org.id == "o1"
        assert org.github_id == 100
        assert org.name == "Test Org"
        assert org.login == "testorg"
        assert org.token_owner_user_id == "u1"


class TestRepository:
    def test_create_repo_with_defaults(self):
        repo = Repository(id="r1", github_id=200, name="repo", full_name="org/repo")
        assert repo.id == "r1"
        assert repo.org_id is None
        assert repo.owner_login == ""
        assert repo.default_branch == "main"
        assert repo.is_selected is True

    def test_create_repo_with_org(self):
        repo = Repository(
            id="r2",
            github_id=201,
            name="repo2",
            full_name="org/repo2",
            org_id="o1",
            owner_login="org",
            default_branch="develop",
        )
        assert repo.org_id == "o1"
        assert repo.default_branch == "develop"
        assert repo.is_selected is True


class TestEolStatus:
    def test_create_eol_status_supported(self):
        status = EolStatus(
            repo_id="r1",
            framework_name="nuxt",
            current_version="3.0.0",
        )
        assert status.is_eol is False
        assert status.eol_date is None
        assert isinstance(status.last_scanned_at, datetime)

    def test_create_eol_status_eol(self):
        eol_date = datetime(2023, 12, 31)
        status = EolStatus(
            repo_id="r1",
            framework_name="nuxt",
            current_version="2.15.8",
            is_eol=True,
            eol_date=eol_date,
        )
        assert status.is_eol is True
        assert status.eol_date == eol_date


class TestScanJob:
    def test_create_scan_job_with_defaults(self):
        job = ScanJob(id="job-1", org_id="octocat", requested_by="octocat")
        assert job.id == "job-1"
        assert job.status == "queued"
        assert job.total_repos == 0
        assert job.completed_repos == 0
        assert job.failed_repos == 0
        assert isinstance(job.created_at, datetime)
        assert isinstance(job.updated_at, datetime)


class TestScanJobRepoProgress:
    def test_create_scan_job_repo_progress_with_defaults(self):
        progress = ScanJobRepoProgress(job_id="job-1", repo_id="repo-1")

        assert progress.job_id == "job-1"
        assert progress.repo_id == "repo-1"
        assert progress.status == "pending"
        assert progress.error_message is None
        assert isinstance(progress.created_at, datetime)
        assert isinstance(progress.updated_at, datetime)


class TestTokenUsageEvent:
    def test_create_token_usage_event(self):
        event = TokenUsageEvent(
            user_id="u1",
            provider="openai",
            model="gpt-5.4",
            input_tokens=120,
            output_tokens=30,
            total_tokens=150,
        )

        assert event.user_id == "u1"
        assert event.provider == "openai"
        assert event.model == "gpt-5.4"
        assert event.total_tokens == 150
        assert isinstance(event.recorded_at, datetime)
