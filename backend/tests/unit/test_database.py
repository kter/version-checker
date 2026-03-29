import pytest

from app.infrastructure.database import get_dsql_hostname, settings


def test_get_dsql_hostname_requires_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "dsql_endpoint", "")

    with pytest.raises(RuntimeError, match="DSQL_ENDPOINT is not configured"):
        get_dsql_hostname()
