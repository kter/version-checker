from unittest.mock import AsyncMock

import pytest

import app.scan_worker_handler as scan_worker_handler


def test_lambda_handler_processes_all_records(monkeypatch):
    process_record = AsyncMock()
    monkeypatch.setattr(scan_worker_handler, "_process_record", process_record)

    result = scan_worker_handler.lambda_handler(
        {"Records": [{"body": "{}"}, {"body": "{}"}]},
        None,
    )

    assert result == {"statusCode": 200}
    assert process_record.await_count == 2


def test_lambda_handler_propagates_worker_failures(monkeypatch):
    process_record = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(scan_worker_handler, "_process_record", process_record)

    with pytest.raises(RuntimeError, match="boom"):
        scan_worker_handler.lambda_handler({"Records": [{"body": "{}"}]}, None)
