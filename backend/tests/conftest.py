"""Shared test fixtures."""

import pytest


@pytest.fixture
def sample_user_data():
    return {
        "id": "test-user-001",
        "github_id": 12345,
        "username": "testuser",
        "email": "test@example.com",
        "role": "admin",
    }


@pytest.fixture
def sample_repo_data():
    return {
        "id": "test-repo-001",
        "github_id": 67890,
        "name": "my-app",
        "full_name": "testorg/my-app",
        "org_id": "test-org-001",
        "owner_login": "testorg",
        "default_branch": "main",
        "is_selected": True,
    }


@pytest.fixture
def sample_org_data():
    return {
        "id": "test-org-001",
        "github_id": 11111,
        "name": "Test Organization",
        "login": "testorg",
    }
