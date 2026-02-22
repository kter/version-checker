import json
from datetime import datetime, timedelta
from typing import List, Optional
from aiobotocore.session import get_session
from app.domain.interfaces import IEolCacheRepository
from app.domain.entities import EolStatus
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
