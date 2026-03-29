from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.database_repo import TokenUsageRepository
from app.api.auth_deps import get_current_user
from app.domain.entities import User
from app.infrastructure.database import get_db_session

router = APIRouter(prefix="/api/v1/usage", tags=["Usage"])


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _current_month_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or _utcnow_naive()
    period_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_start.month == 12:
        period_end = period_start.replace(year=period_start.year + 1, month=1)
    else:
        period_end = period_start.replace(month=period_start.month + 1)
    return period_start, period_end


@router.get("/current-month")
async def get_current_month_usage(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    try:
        period_start, period_end = _current_month_window()
        repository = TokenUsageRepository(session)
        total_tokens = await repository.get_current_month_total_tokens(
            user.id,
            now=period_start,
        )
        return {
            "year_month": period_start.strftime("%Y-%m"),
            "total_tokens": total_tokens,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
