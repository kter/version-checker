"""Unit tests for SQLAlchemy models."""

from datetime import datetime

from app.adapters.models import (
    EolStatusModel,
    OrgModel,
    RepoModel,
    ScanJobModel,
    ScanJobRepoProgressModel,
    TokenUsageEventModel,
    UserModel,
)


class TestUserModel:
    def test_to_domain(self):
        model = UserModel(
            id="u1",
            github_id=123,
            username="alice",
            email="alice@example.com",
            role="admin",
            github_access_token="ghu_test",
            github_refresh_token="ghr_test",
        )
        user = model.to_domain()
        assert user.id == "u1"
        assert user.github_id == 123
        assert user.username == "alice"
        assert user.email == "alice@example.com"
        assert user.role == "admin"
        assert user.github_access_token == "ghu_test"
        assert user.github_refresh_token == "ghr_test"

    def test_to_domain_no_email(self):
        model = UserModel(
            id="u2",
            github_id=456,
            username="bob",
            email=None,
            role="member",
        )
        user = model.to_domain()
        assert user.email is None
        assert user.role == "member"


class TestRepoModel:
    def test_to_domain(self):
        model = RepoModel(
            id="r1",
            github_id=789,
            name="my-app",
            full_name="org/my-app",
            org_id="o1",
            owner_login="org",
            default_branch="develop",
        )
        repo = model.to_domain()
        assert repo.id == "r1"
        assert repo.github_id == 789
        assert repo.name == "my-app"
        assert repo.full_name == "org/my-app"
        assert repo.org_id == "o1"
        assert repo.default_branch == "develop"
        assert repo.is_selected is True

    def test_to_domain_no_org(self):
        model = RepoModel(
            id="r2",
            github_id=101,
            name="personal-repo",
            full_name="user/personal-repo",
            org_id=None,
            owner_login="user",
            default_branch="main",
            is_selected=False,
        )
        repo = model.to_domain()
        assert repo.org_id is None
        assert repo.is_selected is False


class TestOrgModel:
    def test_table_name(self):
        assert OrgModel.__tablename__ == "organizations"

    def test_create_instance(self):
        model = OrgModel(
            id="o1",
            github_id=100,
            name="Test Org",
            login="testorg",
            github_access_token="gho_test",
            token_owner_user_id="u1",
        )
        assert model.id == "o1"
        assert model.login == "testorg"
        assert model.github_access_token == "gho_test"
        assert model.token_owner_user_id == "u1"


class TestEolStatusModel:
    def test_to_domain(self):
        scanned_at = datetime(2026, 3, 28, 10, 0, 0)
        model = EolStatusModel(
            id="s1",
            repo_id="r1",
            framework_name="Nuxt",
            current_version="3.16.0",
            is_eol=False,
            last_scanned_at=scanned_at,
            source_path="apps/web/package.json",
        )

        status = model.to_domain()

        assert status.repo_id == "r1"
        assert status.framework_name == "Nuxt"
        assert status.current_version == "3.16.0"
        assert status.last_scanned_at == scanned_at
        assert status.source_path == "apps/web/package.json"


class TestScanJobModel:
    def test_to_domain(self):
        created_at = datetime(2026, 3, 28, 10, 0, 0)
        updated_at = datetime(2026, 3, 28, 10, 0, 5)
        model = ScanJobModel(
            id="job-1",
            org_id="octocat",
            requested_by="octocat",
            status="running",
            total_repos=4,
            completed_repos=1,
            failed_repos=0,
            started_at=created_at,
            created_at=created_at,
            updated_at=updated_at,
        )

        job = model.to_domain()

        assert job.id == "job-1"
        assert job.org_id == "octocat"
        assert job.requested_by == "octocat"
        assert job.status == "running"
        assert job.total_repos == 4
        assert job.completed_repos == 1
        assert job.created_at == created_at
        assert job.updated_at == updated_at


class TestTokenUsageEventModel:
    def test_to_domain(self):
        recorded_at = datetime(2026, 3, 28, 10, 0, 0)
        model = TokenUsageEventModel(
            id="usage-1",
            user_id="u1",
            provider="openai",
            model="gpt-5.4",
            input_tokens=120,
            output_tokens=30,
            total_tokens=150,
            recorded_at=recorded_at,
        )

        event = model.to_domain()

        assert event.user_id == "u1"
        assert event.provider == "openai"
        assert event.model == "gpt-5.4"
        assert event.input_tokens == 120
        assert event.output_tokens == 30
        assert event.total_tokens == 150
        assert event.recorded_at == recorded_at


class TestScanJobRepoProgressModel:
    def test_to_domain(self):
        created_at = datetime(2026, 3, 28, 10, 0, 0)
        updated_at = datetime(2026, 3, 28, 10, 0, 5)
        model = ScanJobRepoProgressModel(
            job_id="job-1",
            repo_id="repo-1",
            status="completed",
            error_message=None,
            created_at=created_at,
            updated_at=updated_at,
        )

        progress = model.to_domain()

        assert progress.job_id == "job-1"
        assert progress.repo_id == "repo-1"
        assert progress.status == "completed"
        assert progress.error_message is None
        assert progress.created_at == created_at
        assert progress.updated_at == updated_at
