from abc import ABC, abstractmethod
from typing import Optional, List
from app.domain.entities import User, Repository, EolStatus, Organization


class IUserRepository(ABC):
    @abstractmethod
    async def find_by_github_id(self, github_id: int) -> Optional[User]:
        pass

    @abstractmethod
    async def save(self, user: User) -> User:
        pass


class IRepoRepository(ABC):
    @abstractmethod
    async def find_by_org(self, org_id: str) -> List[Repository]:
        pass

    @abstractmethod
    async def save(self, repo: Repository) -> Repository:
        pass


class IEolCacheRepository(ABC):
    """DynamoDB specialized caching repo interface."""

    @abstractmethod
    async def get_eol_status(self, repo_id: str) -> List[EolStatus]:
        pass

    @abstractmethod
    async def set_eol_status(self, status: EolStatus, ttl_seconds: int = 86400) -> None:
        pass
