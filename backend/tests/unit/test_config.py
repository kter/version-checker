"""Unit tests for infrastructure config."""

import os
import pytest
from unittest.mock import patch


class TestSettings:
    def test_default_env_files_include_repo_root_env(self):
        from app.infrastructure.config import BACKEND_DIR, DEFAULT_ENV_FILES, REPO_ROOT

        assert DEFAULT_ENV_FILES == (
            str(REPO_ROOT / ".env"),
            str(BACKEND_DIR / ".env"),
        )

    def test_dsql_hostname_from_arn(self):
        with patch.dict(
            os.environ,
            {
                "DSQL_ENDPOINT": "arn:aws:dsql:ap-northeast-1:123456789012:cluster/abc123def456",
                "DYNAMO_TABLE": "test-table",
            },
            clear=False,
        ):
            # Re-import to pick up new env
            from app.infrastructure.config import Settings

            s = Settings(
                dsql_endpoint="arn:aws:dsql:ap-northeast-1:123456789012:cluster/abc123def456",
                dynamo_table="test-table",
            )
            assert s.dsql_hostname == "abc123def456.dsql.ap-northeast-1.on.aws"

    def test_dsql_hostname_passthrough(self):
        from app.infrastructure.config import Settings

        s = Settings(
            dsql_endpoint="my-cluster.dsql.ap-northeast-1.on.aws",
            dynamo_table="test-table",
        )
        assert s.dsql_hostname == "my-cluster.dsql.ap-northeast-1.on.aws"

    def test_dsql_hostname_different_region(self):
        from app.infrastructure.config import Settings

        s = Settings(
            dsql_endpoint="arn:aws:dsql:us-east-1:123456789012:cluster/xyz789",
            dynamo_table="test-table",
        )
        assert s.dsql_hostname == "xyz789.dsql.us-east-1.on.aws"

    def test_default_values(self):
        with patch.dict(os.environ, clear=True):
            from app.infrastructure.config import Settings

            s = Settings(
                _env_file=None,  # ignore .env file for default test
                dsql_endpoint="",
                dynamo_table="",
            )
            assert s.env == "local"
            assert s.aws_region == "ap-northeast-1"
            assert s.github_client_id is None
            assert s.github_client_secret is None
            assert s.frontend_base_url == "http://localhost:3000"
            assert s.github_redirect_uri == "http://localhost:3000/auth/callback"
            assert s.cors_allow_origins_list == ["http://localhost:3000"]

    def test_cors_allow_origins_list(self):
        from app.infrastructure.config import Settings

        s = Settings(
            dsql_endpoint="",
            dynamo_table="test-table",
            frontend_base_url="https://version-check.dev.devtools.site",
            cors_allow_origins="http://localhost:3000, https://version-check.dev.devtools.site",
        )

        assert (
            s.github_redirect_uri
            == "https://version-check.dev.devtools.site/auth/callback"
        )
        assert s.cors_allow_origins_list == [
            "http://localhost:3000",
            "https://version-check.dev.devtools.site",
        ]
