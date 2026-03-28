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


class IOrgRepository(ABC):
    @abstractmethod
    async def save(self, org: Organization) -> Organization:
        pass

    @abstractmethod
    async def save_all(self, orgs: List[Organization]) -> List[Organization]:
        pass

    @abstractmethod
    async def find_all_with_tokens(self) -> List[Organization]:
        pass


class IRepoRepository(ABC):
    @abstractmethod
    async def find_by_org(self, org_id: str) -> List[Repository]:
        pass

    @abstractmethod
    async def save(self, repo: Repository) -> Repository:
        pass


class IEolStatusRepository(ABC):
    """Persistent scan result repository."""

    @abstractmethod
    async def find_by_repo(self, repo_id: str) -> List[EolStatus]:
        pass

    @abstractmethod
    async def find_by_org(self, org_id: str) -> List[EolStatus]:
        pass

    @abstractmethod
    async def replace_for_repo(self, repo_id: str, statuses: List[EolStatus]) -> None:
        pass
