"""Unit tests for SQLAlchemy models."""

from datetime import datetime

from app.adapters.models import (
    EolStatusModel,
    OrgModel,
    RepoModel,
    ScanJobModel,
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
        )
        user = model.to_domain()
        assert user.id == "u1"
        assert user.github_id == 123
        assert user.username == "alice"
        assert user.email == "alice@example.com"
        assert user.role == "admin"

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

    def test_to_domain_no_org(self):
        model = RepoModel(
            id="r2",
            github_id=101,
            name="personal-repo",
            full_name="user/personal-repo",
            org_id=None,
            owner_login="user",
            default_branch="main",
        )
        repo = model.to_domain()
        assert repo.org_id is None


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
        )
        assert model.id == "o1"
        assert model.login == "testorg"
        assert model.github_access_token == "gho_test"


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
