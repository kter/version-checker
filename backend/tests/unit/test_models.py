"""Unit tests for SQLAlchemy models."""

from app.adapters.models import UserModel, RepoModel, OrgModel


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
        )
        assert model.id == "o1"
        assert model.login == "testorg"
