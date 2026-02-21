from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
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
        user_id = user.id if user.id else str(uuid.uuid4())
        
        # Upsert operation compliant with DSQL limits (avoiding complex transactions)
        stmt = insert(UserModel).values(
            id=user_id,
            github_id=user.github_id,
            username=user.username,
            email=user.email,
            role=user.role
        ).on_conflict_do_update(
            index_elements=['github_id'],
            set_={
                'username': user.username,
                'email': user.email,
                'role': user.role
            }
        ).returning(UserModel)
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one().to_domain()

class RepoRepository(IRepoRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_org(self, org_id: str) -> List[Repository]:
        result = await self.session.execute(
            select(RepoModel).where(RepoModel.org_id == org_id)
        )
        return [r.to_domain() for r in result.scalars().all()]

    async def save(self, repo: Repository) -> Repository:
        repo_id = repo.id if repo.id else str(uuid.uuid4())
        
        stmt = insert(RepoModel).values(
            id=repo_id,
            github_id=repo.github_id,
            name=repo.name,
            full_name=repo.full_name,
            org_id=repo.org_id,
            owner_login=repo.owner_login,
            default_branch=repo.default_branch
        ).on_conflict_do_update(
            index_elements=['github_id'],
            set_={
                'name': repo.name,
                'full_name': repo.full_name,
                'owner_login': repo.owner_login,
                'default_branch': repo.default_branch
            }
        ).returning(RepoModel)
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one().to_domain()
