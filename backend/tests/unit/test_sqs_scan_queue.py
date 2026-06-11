"""Unit tests for the SQS scan queue adapter."""

import json
from unittest.mock import MagicMock

import pytest

from app.adapters.sqs_scan_queue import SQS_BATCH_SIZE, SqsScanQueue, _chunked

QUEUE_URL = "https://sqs.ap-northeast-1.amazonaws.com/123456789012/scan-queue"


def _make_queue(client: MagicMock) -> SqsScanQueue:
    queue = SqsScanQueue(queue_url=QUEUE_URL, region_name="ap-northeast-1")
    queue._get_client = lambda: client
    return queue


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_sends_compact_json_body(self):
        client = MagicMock()
        queue = _make_queue(client)

        await queue.send_message({"type": "bootstrap", "job_id": "job-1"})

        client.send_message.assert_called_once_with(
            QueueUrl=QUEUE_URL,
            MessageBody='{"type":"bootstrap","job_id":"job-1"}',
        )

    @pytest.mark.asyncio
    async def test_raises_when_queue_url_is_not_configured(self):
        queue = SqsScanQueue(queue_url="", region_name="ap-northeast-1")

        with pytest.raises(RuntimeError, match="SCAN_QUEUE_URL is not configured"):
            await queue.send_message({"type": "bootstrap"})


class TestSendMessages:
    @pytest.mark.asyncio
    async def test_empty_payload_list_is_a_no_op(self):
        client = MagicMock()
        queue = _make_queue(client)

        await queue.send_messages([])

        client.send_message_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_when_queue_url_is_not_configured(self):
        queue = SqsScanQueue(queue_url="", region_name="ap-northeast-1")

        with pytest.raises(RuntimeError, match="SCAN_QUEUE_URL is not configured"):
            await queue.send_messages([{"repo_id": "r1"}])

    @pytest.mark.asyncio
    async def test_batch_size_boundary_sends_single_batch(self):
        client = MagicMock()
        client.send_message_batch.return_value = {"Successful": []}
        queue = _make_queue(client)
        payloads = [{"repo_id": f"r{i}"} for i in range(SQS_BATCH_SIZE)]

        await queue.send_messages(payloads)

        assert client.send_message_batch.call_count == 1
        entries = client.send_message_batch.call_args.kwargs["Entries"]
        assert [entry["Id"] for entry in entries] == [
            str(i) for i in range(SQS_BATCH_SIZE)
        ]
        assert json.loads(entries[0]["MessageBody"]) == {"repo_id": "r0"}

    @pytest.mark.asyncio
    async def test_over_batch_size_splits_into_multiple_batches(self):
        client = MagicMock()
        client.send_message_batch.return_value = {"Successful": []}
        queue = _make_queue(client)
        payloads = [{"repo_id": f"r{i}"} for i in range(SQS_BATCH_SIZE + 1)]

        await queue.send_messages(payloads)

        assert client.send_message_batch.call_count == 2
        second_entries = client.send_message_batch.call_args_list[1].kwargs["Entries"]
        assert len(second_entries) == 1
        assert json.loads(second_entries[0]["MessageBody"]) == {
            "repo_id": f"r{SQS_BATCH_SIZE}"
        }

    @pytest.mark.asyncio
    async def test_failed_entries_raise_runtime_error(self):
        client = MagicMock()
        client.send_message_batch.return_value = {
            "Failed": [{"Id": "0", "Message": "InternalError"}]
        }
        queue = _make_queue(client)

        with pytest.raises(RuntimeError, match="InternalError"):
            await queue.send_messages([{"repo_id": "r1"}])

    @pytest.mark.asyncio
    async def test_failed_entry_without_message_falls_back_to_id(self):
        client = MagicMock()
        client.send_message_batch.return_value = {"Failed": [{"Id": "3"}]}
        queue = _make_queue(client)

        with pytest.raises(RuntimeError, match="3"):
            await queue.send_messages([{"repo_id": "r1"}])


class TestChunked:
    def test_exact_multiple_of_chunk_size(self):
        items = [{"i": i} for i in range(20)]
        chunks = list(_chunked(items, 10))
        assert [len(chunk) for chunk in chunks] == [10, 10]

    def test_remainder_goes_into_final_chunk(self):
        items = [{"i": i} for i in range(11)]
        chunks = list(_chunked(items, 10))
        assert [len(chunk) for chunk in chunks] == [10, 1]

    def test_empty_input_yields_no_chunks(self):
        assert list(_chunked([], 10)) == []
