import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.dynamo_repo import DynamoRepoListCacheRepository
from app.domain.entities import Repository


def _mock_client_session(client: AsyncMock) -> MagicMock:
    session = MagicMock()
    context_manager = AsyncMock()
    context_manager.__aenter__.return_value = client
    context_manager.__aexit__.return_value = None
    session.create_client.return_value = context_manager
    return session


class TestDynamoRepoListCacheRepository:
    @pytest.mark.asyncio
    async def test_get_repositories_returns_none_when_table_is_not_configured(self):
        repository = DynamoRepoListCacheRepository(table_name="")

        result = await repository.get_repositories("octocat")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_repositories_deserializes_cached_payload(self):
        client = AsyncMock()
        client.get_item.return_value = {
            "Item": {
                "expires_at": {
                    "N": str(
                        int((datetime.now(UTC) + timedelta(seconds=60)).timestamp())
                    )
                },
                "repositories_json": {
                    "S": json.dumps(
                        [
                            {
                                "github_id": 1,
                                "name": "app",
                                "full_name": "octocat/app",
                                "org_id": "octocat",
                                "owner_login": "octocat",
                                "default_branch": "main",
                                "updated_at": "2026-03-30T09:15:00+00:00",
                            }
                        ]
                    )
                },
            }
        }

        repository = DynamoRepoListCacheRepository(table_name="repo-cache")
        repository.session = _mock_client_session(client)

        result = await repository.get_repositories("octocat")

        assert result == [
            Repository(
                id="",
                github_id=1,
                name="app",
                full_name="octocat/app",
                org_id="octocat",
                owner_login="octocat",
                default_branch="main",
                is_selected=False,
                updated_at=datetime(2026, 3, 30, 9, 15, 0, tzinfo=UTC),
            )
        ]
        client.get_item.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_repositories_persists_payload_with_ttl(self):
        client = AsyncMock()
        repository = DynamoRepoListCacheRepository(
            table_name="repo-cache",
            ttl_seconds=180,
        )
        repository.session = _mock_client_session(client)

        await repository.set_repositories(
            "octocat",
            [
                Repository(
                    id="repo-1",
                    github_id=1,
                    name="app",
                    full_name="octocat/app",
                    org_id="octocat",
                    owner_login="octocat",
                    default_branch="main",
                    is_selected=True,
                    updated_at=datetime(2026, 3, 30, 9, 15, 0, tzinfo=UTC),
                )
            ],
        )

        client.put_item.assert_awaited_once()
        put_item_kwargs = client.put_item.await_args.kwargs
        assert put_item_kwargs["TableName"] == "repo-cache"
        assert put_item_kwargs["Item"]["cache_key"]["S"] == "ORG#octocat"
        assert (
            json.loads(put_item_kwargs["Item"]["repositories_json"]["S"])[0][
                "full_name"
            ]
            == "octocat/app"
        )
        assert (
            json.loads(put_item_kwargs["Item"]["repositories_json"]["S"])[0][
                "updated_at"
            ]
            == "2026-03-30T09:15:00+00:00"
        )
        assert int(put_item_kwargs["Item"]["expires_at"]["N"]) > int(
            datetime.now(UTC).timestamp()
        )
