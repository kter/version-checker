import asyncio
import json
from typing import Any, Dict, Iterable, List

import boto3

from app.infrastructure.config import settings

SQS_BATCH_SIZE = 10


class SqsScanQueue:
    def __init__(
        self,
        queue_url: str = settings.scan_queue_url,
        region_name: str = settings.aws_region,
    ):
        self.queue_url = queue_url
        self.region_name = region_name

    def _get_client(self):
        return boto3.client("sqs", region_name=self.region_name)

    async def send_message(self, payload: Dict[str, Any]) -> None:
        if not self.queue_url:
            raise RuntimeError("SCAN_QUEUE_URL is not configured")

        body = json.dumps(payload, separators=(",", ":"))
        await asyncio.to_thread(
            self._get_client().send_message,
            QueueUrl=self.queue_url,
            MessageBody=body,
        )

    async def send_messages(self, payloads: List[Dict[str, Any]]) -> None:
        if not payloads:
            return
        if not self.queue_url:
            raise RuntimeError("SCAN_QUEUE_URL is not configured")

        for batch in _chunked(payloads, SQS_BATCH_SIZE):
            entries = [
                {
                    "Id": str(index),
                    "MessageBody": json.dumps(payload, separators=(",", ":")),
                }
                for index, payload in enumerate(batch)
            ]
            response = await asyncio.to_thread(
                self._get_client().send_message_batch,
                QueueUrl=self.queue_url,
                Entries=entries,
            )
            if response.get("Failed"):
                failed = ", ".join(
                    item.get("Message", item.get("Id", "unknown"))
                    for item in response["Failed"]
                )
                raise RuntimeError(f"Failed to publish scan messages: {failed}")


def _chunked(items: List[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]
