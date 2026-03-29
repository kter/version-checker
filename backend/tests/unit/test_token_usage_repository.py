from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.database_repo import TokenUsageRepository


class TestTokenUsageRepository:
    @pytest.mark.asyncio
    async def test_get_current_month_total_tokens_uses_current_month_window(self):
        session = AsyncMock()
        result = MagicMock()
        result.scalar.return_value = 321
        session.execute = AsyncMock(return_value=result)

        repository = TokenUsageRepository(session)

        total = await repository.get_current_month_total_tokens(
            "user-1",
            now=datetime(2026, 3, 29, 12, 0, 0),
        )

        assert total == 321
        statement = session.execute.await_args.args[0]
        params = statement.compile().params
        assert "user-1" in params.values()
        assert datetime(2026, 3, 1, 0, 0, 0) in params.values()
        assert datetime(2026, 4, 1, 0, 0, 0) in params.values()

    @pytest.mark.asyncio
    async def test_get_current_month_total_tokens_returns_zero_without_events(self):
        session = AsyncMock()
        result = MagicMock()
        result.scalar.return_value = None
        session.execute = AsyncMock(return_value=result)

        repository = TokenUsageRepository(session)

        total = await repository.get_current_month_total_tokens(
            "user-1",
            now=datetime(2026, 3, 29, 12, 0, 0),
        )

        assert total == 0
