from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import uuid
from app.domain.interfaces import IUserRepository, IRepoRepository
from app.domain.entities import User, Repository
from app.adapters.models import UserModel, RepoModel


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

        await self.session.refresh(model)
        return model.to_domain()


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

        await self.session.refresh(model)
        return model.to_domain()
