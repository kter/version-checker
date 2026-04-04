from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, desc, delete, func, select, update
import uuid
from app.domain.interfaces import (
    IUserRepository,
    IOrgRepository,
    IRepoRepository,
    IEolStatusRepository,
    IScanJobRepository,
    ITokenUsageRepository,
)
from app.domain.entities import (
    ACTIVE_SCAN_JOB_STATUSES,
    SCAN_JOB_REPO_STATUS_COMPLETED,
    SCAN_JOB_REPO_STATUS_FAILED,
    SCAN_JOB_REPO_STATUS_PENDING,
    SCAN_JOB_STATUS_COMPLETED,
    ScanJobRepoProgress,
    User,
    Organization,
    Repository,
    EolStatus,
    ScanJob,
    TokenUsageEvent,
)
from app.adapters.models import (
    UserModel,
    OrgModel,
    RepoModel,
    EolStatusModel,
    ScanJobModel,
    ScanJobRepoProgressModel,
    TokenUsageEventModel,
)
from datetime import UTC, datetime


class UserRepository(IUserRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_id(self, user_id: str) -> Optional[User]:
        result = await self.session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()
        if model:
            return model.to_domain()
        return None

    async def find_by_github_id(self, github_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(UserModel).where(UserModel.github_id == github_id)
        )
        model = result.scalar_one_or_none()
        if model:
            return model.to_domain()
        return None

    async def save(self, user: User) -> User:
        # Check if user with this github_id already exists
        existing = await self.session.execute(
            select(UserModel).where(UserModel.github_id == user.github_id)
        )
        model = existing.scalar_one_or_none()

        if model:
            # Update existing
            model.username = user.username
            model.email = user.email
            model.role = user.role
            model.github_access_token = user.github_access_token
            model.github_refresh_token = user.github_refresh_token
            model.github_access_token_expires_at = user.github_access_token_expires_at
            model.github_refresh_token_expires_at = user.github_refresh_token_expires_at
        else:
            # Insert new
            model = UserModel(
                id=user.id if user.id else str(uuid.uuid4()),
                github_id=user.github_id,
                username=user.username,
                email=user.email,
                role=user.role,
                github_access_token=user.github_access_token,
                github_refresh_token=user.github_refresh_token,
                github_access_token_expires_at=user.github_access_token_expires_at,
                github_refresh_token_expires_at=user.github_refresh_token_expires_at,
            )
            self.session.add(model)

        await self.session.flush()
        return model.to_domain()


class OrgRepository(IOrgRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, org: Organization) -> Organization:
        existing = await self.session.execute(
            select(OrgModel).where(OrgModel.login == org.login)
        )
        model = existing.scalar_one_or_none()

        if model:
            model.github_id = org.github_id
            model.name = org.name
            model.github_access_token = org.github_access_token
            model.token_owner_user_id = org.token_owner_user_id
        else:
            model = OrgModel(
                id=org.id,
                github_id=org.github_id,
                name=org.name,
                login=org.login,
                github_access_token=org.github_access_token,
                token_owner_user_id=org.token_owner_user_id,
            )
            self.session.add(model)

        await self.session.flush()
        return model.to_domain()

    async def save_all(self, orgs: List[Organization]) -> List[Organization]:
        saved = []
        for org in orgs:
            saved.append(await self.save(org))
        return saved

    async def find_all_with_tokens(self) -> List[Organization]:
        result = await self.session.execute(
            select(OrgModel).where(
                OrgModel.token_owner_user_id.is_not(None)
                | OrgModel.github_access_token.is_not(None)
            )
        )
        return [org.to_domain() for org in result.scalars().all()]

    async def find_by_login(self, login: str) -> Optional[Organization]:
        result = await self.session.execute(
            select(OrgModel).where(OrgModel.login == login)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def find_by_github_id(self, github_id: int) -> Optional[Organization]:
        result = await self.session.execute(
            select(OrgModel).where(OrgModel.github_id == github_id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None


class RepoRepository(IRepoRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_org(self, org_id: str) -> List[Repository]:
        result = await self.session.execute(
            select(RepoModel).where(RepoModel.org_id == org_id)
        )
        return [r.to_domain() for r in result.scalars().all()]

    async def find_selected_by_org(self, org_id: str) -> List[Repository]:
        result = await self.session.execute(
            select(RepoModel)
            .where(RepoModel.org_id == org_id)
            .where(RepoModel.is_selected.is_(True))
        )
        return [r.to_domain() for r in result.scalars().all()]

    async def save(self, repo: Repository) -> Repository:
        # Check if repo with this github_id already exists
        existing = await self.session.execute(
            select(RepoModel).where(RepoModel.github_id == repo.github_id)
        )
        model = existing.scalar_one_or_none()

        if model:
            model.name = repo.name
            model.full_name = repo.full_name
            model.org_id = repo.org_id
            model.owner_login = repo.owner_login
            model.default_branch = repo.default_branch
            model.is_selected = repo.is_selected
        else:
            model = RepoModel(
                id=repo.id if repo.id else str(uuid.uuid4()),
                github_id=repo.github_id,
                name=repo.name,
                full_name=repo.full_name,
                org_id=repo.org_id,
                owner_login=repo.owner_login,
                default_branch=repo.default_branch,
                is_selected=repo.is_selected,
            )
            self.session.add(model)

        await self.session.flush()
        return model.to_domain()

    async def find_by_id(self, repo_id: str) -> Optional[Repository]:
        result = await self.session.execute(
            select(RepoModel).where(RepoModel.id == repo_id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def replace_selection(
        self, org_id: str, selected_repo_ids: List[str]
    ) -> None:
        await self.session.execute(
            update(RepoModel)
            .where(RepoModel.org_id == org_id)
            .values(is_selected=False)
        )
        if selected_repo_ids:
            await self.session.execute(
                update(RepoModel)
                .where(RepoModel.org_id == org_id)
                .where(RepoModel.id.in_(selected_repo_ids))
                .values(is_selected=True)
            )
        await self.session.flush()


class EolStatusRepository(IEolStatusRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_repo(self, repo_id: str) -> List[EolStatus]:
        result = await self.session.execute(
            select(EolStatusModel).where(EolStatusModel.repo_id == repo_id)
        )
        return [status.to_domain() for status in result.scalars().all()]

    async def find_by_org(self, org_id: str) -> List[EolStatus]:
        result = await self.session.execute(
            select(EolStatusModel)
            .join(RepoModel, RepoModel.id == EolStatusModel.repo_id)
            .where(RepoModel.org_id == org_id)
        )
        return [status.to_domain() for status in result.scalars().all()]

    async def replace_for_repo(self, repo_id: str, statuses: List[EolStatus]) -> None:
        await self.session.execute(
            delete(EolStatusModel).where(EolStatusModel.repo_id == repo_id)
        )

        for status in statuses:
            self.session.add(
                EolStatusModel(
                    id=str(uuid.uuid4()),
                    repo_id=repo_id,
                    framework_name=status.framework_name,
                    current_version=status.current_version,
                    eol_date=status.eol_date,
                    is_eol=status.is_eol,
                    last_scanned_at=status.last_scanned_at,
                    source_path=status.source_path,
                )
            )

        await self.session.flush()


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _current_month_bounds(now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    current = now or _utcnow_naive()
    period_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_start.month == 12:
        period_end = period_start.replace(year=period_start.year + 1, month=1)
    else:
        period_end = period_start.replace(month=period_start.month + 1)
    return period_start, period_end


class ScanJobRepository(IScanJobRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job: ScanJob) -> ScanJob:
        model = ScanJobModel(
            id=job.id,
            org_id=job.org_id,
            requested_by=job.requested_by,
            status=job.status,
            total_repos=job.total_repos,
            completed_repos=job.completed_repos,
            failed_repos=job.failed_repos,
            started_at=job.started_at,
            finished_at=job.finished_at,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        self.session.add(model)
        await self.session.flush()
        return model.to_domain()

    def _progress_summary_subquery(self):
        return (
            select(
                ScanJobRepoProgressModel.job_id.label("job_id"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ScanJobRepoProgressModel.status
                                == SCAN_JOB_REPO_STATUS_COMPLETED,
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("completed_repos"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ScanJobRepoProgressModel.status
                                == SCAN_JOB_REPO_STATUS_FAILED,
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("failed_repos"),
            )
            .group_by(ScanJobRepoProgressModel.job_id)
            .subquery()
        )

    def _scan_job_query(self):
        progress_summary = self._progress_summary_subquery()
        return select(
            ScanJobModel,
            func.coalesce(
                progress_summary.c.completed_repos,
                ScanJobModel.completed_repos,
            ).label("completed_repos"),
            func.coalesce(
                progress_summary.c.failed_repos,
                ScanJobModel.failed_repos,
            ).label("failed_repos"),
        ).outerjoin(progress_summary, progress_summary.c.job_id == ScanJobModel.id)

    def _to_scan_job(
        self,
        model: ScanJobModel,
        completed_repos: Optional[int],
        failed_repos: Optional[int],
    ) -> ScanJob:
        job = model.to_domain()
        job.completed_repos = int(completed_repos or 0)
        job.failed_repos = int(failed_repos or 0)
        return job

    async def _fetch_scan_job(self, statement) -> Optional[ScanJob]:
        result = await self.session.execute(statement)
        row = result.first()
        if not row:
            return None
        model, completed_repos, failed_repos = row
        return self._to_scan_job(model, completed_repos, failed_repos)

    async def _get_progress_counts(self, job_id: str) -> tuple[int, int]:
        result = await self.session.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ScanJobRepoProgressModel.status
                                == SCAN_JOB_REPO_STATUS_COMPLETED,
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ScanJobRepoProgressModel.status
                                == SCAN_JOB_REPO_STATUS_FAILED,
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
            ).where(ScanJobRepoProgressModel.job_id == job_id)
        )
        completed_repos, failed_repos = result.one()
        return int(completed_repos or 0), int(failed_repos or 0)

    async def find_by_id(self, job_id: str) -> Optional[ScanJob]:
        return await self._fetch_scan_job(
            self._scan_job_query().where(ScanJobModel.id == job_id)
        )

    async def find_latest_by_org(self, org_id: str) -> Optional[ScanJob]:
        return await self._fetch_scan_job(
            self._scan_job_query()
            .where(ScanJobModel.org_id == org_id)
            .order_by(desc(ScanJobModel.created_at))
            .limit(1)
        )

    async def find_active_by_org(self, org_id: str) -> Optional[ScanJob]:
        return await self._fetch_scan_job(
            self._scan_job_query()
            .where(ScanJobModel.org_id == org_id)
            .where(ScanJobModel.status.in_(ACTIVE_SCAN_JOB_STATUSES))
            .order_by(desc(ScanJobModel.created_at))
            .limit(1)
        )

    async def start(self, job_id: str, total_repos: int) -> Optional[ScanJob]:
        now = _utcnow_naive()
        await self.session.execute(
            update(ScanJobModel)
            .where(ScanJobModel.id == job_id)
            .values(
                status="running",
                total_repos=total_repos,
                completed_repos=0,
                failed_repos=0,
                started_at=now,
                finished_at=None,
                updated_at=now,
                error_message=None,
            )
        )
        await self.session.flush()
        return await self.find_by_id(job_id)

    async def mark_completed(self, job_id: str) -> Optional[ScanJob]:
        return await self.finalize(job_id, SCAN_JOB_STATUS_COMPLETED)

    async def seed_repo_progress(self, job_id: str, repo_ids: List[str]) -> None:
        if not repo_ids:
            return

        now = _utcnow_naive()
        existing = await self.session.execute(
            select(ScanJobRepoProgressModel.repo_id).where(
                ScanJobRepoProgressModel.job_id == job_id,
                ScanJobRepoProgressModel.repo_id.in_(repo_ids),
            )
        )
        existing_repo_ids = set(existing.scalars().all())

        for repo_id in repo_ids:
            if repo_id in existing_repo_ids:
                continue
            self.session.add(
                ScanJobRepoProgressModel(
                    job_id=job_id,
                    repo_id=repo_id,
                    status=SCAN_JOB_REPO_STATUS_PENDING,
                    created_at=now,
                    updated_at=now,
                )
            )
        await self.session.flush()

    async def find_repo_progress(
        self, job_id: str, repo_id: str
    ) -> Optional[ScanJobRepoProgress]:
        result = await self.session.execute(
            select(ScanJobRepoProgressModel).where(
                ScanJobRepoProgressModel.job_id == job_id,
                ScanJobRepoProgressModel.repo_id == repo_id,
            )
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def record_repo_success(self, job_id: str, repo_id: str) -> Optional[ScanJob]:
        now = _utcnow_naive()
        progress_update = await self.session.execute(
            update(ScanJobRepoProgressModel)
            .where(ScanJobRepoProgressModel.job_id == job_id)
            .where(ScanJobRepoProgressModel.repo_id == repo_id)
            .where(ScanJobRepoProgressModel.status == SCAN_JOB_REPO_STATUS_PENDING)
            .values(
                status=SCAN_JOB_REPO_STATUS_COMPLETED,
                error_message=None,
                updated_at=now,
            )
        )
        if progress_update.rowcount:
            await self.session.execute(
                update(ScanJobModel)
                .where(ScanJobModel.id == job_id)
                .values(updated_at=now)
            )
            await self.session.flush()
        return await self.find_by_id(job_id)

    async def record_repo_failure(
        self, job_id: str, repo_id: str, error_message: Optional[str]
    ) -> Optional[ScanJob]:
        now = _utcnow_naive()
        progress_update = await self.session.execute(
            update(ScanJobRepoProgressModel)
            .where(ScanJobRepoProgressModel.job_id == job_id)
            .where(ScanJobRepoProgressModel.repo_id == repo_id)
            .where(ScanJobRepoProgressModel.status == SCAN_JOB_REPO_STATUS_PENDING)
            .values(
                status=SCAN_JOB_REPO_STATUS_FAILED,
                error_message=error_message,
                updated_at=now,
            )
        )
        if progress_update.rowcount:
            await self.session.execute(
                update(ScanJobModel)
                .where(ScanJobModel.id == job_id)
                .values(updated_at=now, error_message=error_message)
            )
            await self.session.flush()
        return await self.find_by_id(job_id)

    async def finalize(
        self, job_id: str, status: str, error_message: Optional[str] = None
    ) -> Optional[ScanJob]:
        now = _utcnow_naive()
        completed_repos, failed_repos = await self._get_progress_counts(job_id)
        values = {
            "status": status,
            "completed_repos": completed_repos,
            "failed_repos": failed_repos,
            "finished_at": now,
            "updated_at": now,
            "error_message": error_message,
        }
        await self.session.execute(
            update(ScanJobModel)
            .where(ScanJobModel.id == job_id)
            .where(ScanJobModel.status.in_(ACTIVE_SCAN_JOB_STATUSES))
            .values(**values)
        )
        await self.session.flush()
        return await self.find_by_id(job_id)


class TokenUsageRepository(ITokenUsageRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, event: TokenUsageEvent) -> TokenUsageEvent:
        model = TokenUsageEventModel(
            id=str(uuid.uuid4()),
            user_id=event.user_id,
            provider=event.provider,
            model=event.model,
            input_tokens=event.input_tokens,
            output_tokens=event.output_tokens,
            total_tokens=event.total_tokens,
            recorded_at=event.recorded_at,
        )
        self.session.add(model)
        await self.session.flush()
        return model.to_domain()

    async def get_current_month_total_tokens(
        self, user_id: str, now: Optional[datetime] = None
    ) -> int:
        period_start, period_end = _current_month_bounds(now)
        result = await self.session.execute(
            select(func.coalesce(func.sum(TokenUsageEventModel.total_tokens), 0)).where(
                TokenUsageEventModel.user_id == user_id,
                TokenUsageEventModel.recorded_at >= period_start,
                TokenUsageEventModel.recorded_at < period_end,
            )
        )
        return int(result.scalar() or 0)
