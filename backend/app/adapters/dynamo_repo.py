import json
from datetime import UTC, datetime, timedelta
from typing import List, Optional
from aiobotocore.session import get_session
from app.domain.interfaces import IEolCacheRepository, IRepoListCacheRepository
from app.domain.entities import EolStatus, Repository
from app.infrastructure.config import settings


class DynamoEolCacheRepository(IEolCacheRepository):
    def __init__(self, table_name: str = settings.dynamo_table):
        self.table_name = table_name
        self.session = get_session()

    async def get_eol_status(self, repo_id: str) -> List[EolStatus]:
        async with self.session.create_client(
            "dynamodb",
            region_name=settings.aws_region,
            # In local, we might use endpoint_url if LocalStack is used,
            # but per instructions, local connects to AWS dev directly.
        ) as client:
            response = await client.query(
                TableName=self.table_name,
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": {"S": f"REPO#{repo_id}"}},
            )

            results = []
            for item in response.get("Items", []):
                # Only include valid items based on TTL if the DB hasn't cleared them yet
                expires_at = int(item.get("expires_at", {}).get("N", "0"))
                if expires_at > int(datetime.utcnow().timestamp()):
                    status = EolStatus(
                        repo_id=repo_id,
                        framework_name=item.get("framework_name", {}).get("S", ""),
                        current_version=item.get("current_version", {}).get("S", ""),
                        eol_date=(
                            datetime.fromisoformat(item["eol_date"]["S"])
                            if "eol_date" in item
                            else None
                        ),
                        is_eol=item.get("is_eol", {}).get("BOOL", False),
                        last_scanned_at=datetime.fromisoformat(
                            item["last_scanned_at"]["S"]
                        ),
                    )
                    results.append(status)
            return results

    async def set_eol_status(self, status: EolStatus, ttl_seconds: int = 86400) -> None:
        expires_at = int(
            (datetime.utcnow() + timedelta(seconds=ttl_seconds)).timestamp()
        )

        item = {
            "pk": {"S": f"REPO#{status.repo_id}"},
            "sk": {"S": f"FRAMEWORK#{status.framework_name}"},
            "framework_name": {"S": status.framework_name},
            "current_version": {"S": status.current_version},
            "is_eol": {"BOOL": status.is_eol},
            "last_scanned_at": {"S": status.last_scanned_at.isoformat()},
            "expires_at": {"N": str(expires_at)},
        }

        if status.eol_date:
            item["eol_date"] = {"S": status.eol_date.isoformat()}

        async with self.session.create_client(
            "dynamodb", region_name=settings.aws_region
        ) as client:
            await client.put_item(TableName=self.table_name, Item=item)


class DynamoRepoListCacheRepository(IRepoListCacheRepository):
    def __init__(
        self,
        table_name: str = settings.repo_cache_table,
        ttl_seconds: int = settings.repo_cache_ttl_seconds,
    ):
        self.table_name = table_name
        self.ttl_seconds = ttl_seconds
        self.session = get_session()

    async def get_repositories(self, org_id: str) -> Optional[List[Repository]]:
        if not self.table_name:
            return None

        async with self.session.create_client(
            "dynamodb",
            region_name=settings.aws_region,
        ) as client:
            response = await client.get_item(
                TableName=self.table_name,
                Key={"cache_key": {"S": self._cache_key(org_id)}},
            )

        item = response.get("Item")
        if not item:
            return None

        expires_at = int(item.get("expires_at", {}).get("N", "0"))
        if expires_at <= int(datetime.now(UTC).timestamp()):
            return None

        payload = item.get("repositories_json", {}).get("S")
        if not payload:
            return None

        try:
            repositories = json.loads(payload)
        except json.JSONDecodeError:
            return None

        return [
            Repository(
                id="",
                github_id=int(repository["github_id"]),
                name=repository["name"],
                full_name=repository["full_name"],
                org_id=repository.get("org_id") or org_id,
                owner_login=repository.get("owner_login", ""),
                default_branch=repository.get("default_branch") or "main",
                is_selected=False,
                updated_at=(
                    datetime.fromisoformat(repository["updated_at"])
                    if repository.get("updated_at")
                    else None
                ),
            )
            for repository in repositories
        ]

    async def set_repositories(
        self, org_id: str, repositories: List[Repository]
    ) -> None:
        if not self.table_name:
            return

        expires_at = int(
            (datetime.now(UTC) + timedelta(seconds=self.ttl_seconds)).timestamp()
        )
        payload = json.dumps(
            [
                {
                    "github_id": repository.github_id,
                    "name": repository.name,
                    "full_name": repository.full_name,
                    "org_id": repository.org_id,
                    "owner_login": repository.owner_login,
                    "default_branch": repository.default_branch,
                    "updated_at": (
                        repository.updated_at.isoformat()
                        if repository.updated_at
                        else None
                    ),
                }
                for repository in repositories
            ],
            separators=(",", ":"),
        )

        item = {
            "cache_key": {"S": self._cache_key(org_id)},
            "org_id": {"S": org_id},
            "repositories_json": {"S": payload},
            "expires_at": {"N": str(expires_at)},
            "updated_at": {"S": datetime.now(UTC).isoformat()},
        }

        async with self.session.create_client(
            "dynamodb",
            region_name=settings.aws_region,
        ) as client:
            await client.put_item(TableName=self.table_name, Item=item)

    @staticmethod
    def _cache_key(org_id: str) -> str:
        return f"ORG#{org_id}"
