from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import uuid
from app.domain.interfaces import (
    IUserRepository,
    IOrgRepository,
    IRepoRepository,
    IEolStatusRepository,
)
from app.domain.entities import User, Organization, Repository, EolStatus
from app.adapters.models import UserModel, OrgModel, RepoModel, EolStatusModel


class UserRepository(IUserRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

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
        else:
            # Insert new
            model = UserModel(
                id=user.id if user.id else str(uuid.uuid4()),
                github_id=user.github_id,
                username=user.username,
                email=user.email,
                role=user.role,
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
        else:
            model = OrgModel(
                id=org.id,
                github_id=org.github_id,
                name=org.name,
                login=org.login,
                github_access_token=org.github_access_token,
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
            select(OrgModel).where(OrgModel.github_access_token.is_not(None))
        )
        return [org.to_domain() for org in result.scalars().all()]


class RepoRepository(IRepoRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_org(self, org_id: str) -> List[Repository]:
        result = await self.session.execute(
            select(RepoModel).where(RepoModel.org_id == org_id)
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
        else:
            model = RepoModel(
                id=repo.id if repo.id else str(uuid.uuid4()),
                github_id=repo.github_id,
                name=repo.name,
                full_name=repo.full_name,
                org_id=repo.org_id,
                owner_login=repo.owner_login,
                default_branch=repo.default_branch,
            )
            self.session.add(model)

        await self.session.flush()
        return model.to_domain()


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
