from abc import ABC, abstractmethod
from typing import Optional, List
from app.domain.entities import User, Repository, EolStatus, Organization, ScanJob


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

    @abstractmethod
    async def find_by_login(self, login: str) -> Optional[Organization]:
        pass


class IRepoRepository(ABC):
    @abstractmethod
    async def find_by_org(self, org_id: str) -> List[Repository]:
        pass

    @abstractmethod
    async def save(self, repo: Repository) -> Repository:
        pass

    @abstractmethod
    async def find_by_id(self, repo_id: str) -> Optional[Repository]:
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


class IScanJobRepository(ABC):
    @abstractmethod
    async def create(self, job: ScanJob) -> ScanJob:
        pass

    @abstractmethod
    async def find_by_id(self, job_id: str) -> Optional[ScanJob]:
        pass

    @abstractmethod
    async def find_latest_by_org(self, org_id: str) -> Optional[ScanJob]:
        pass

    @abstractmethod
    async def find_active_by_org(self, org_id: str) -> Optional[ScanJob]:
        pass

    @abstractmethod
    async def start(self, job_id: str, total_repos: int) -> Optional[ScanJob]:
        pass

    @abstractmethod
    async def mark_completed(self, job_id: str) -> Optional[ScanJob]:
        pass

    @abstractmethod
    async def record_repo_success(self, job_id: str) -> Optional[ScanJob]:
        pass

    @abstractmethod
    async def record_repo_failure(
        self, job_id: str, error_message: Optional[str]
    ) -> Optional[ScanJob]:
        pass

    @abstractmethod
    async def finalize(
        self, job_id: str, status: str, error_message: Optional[str] = None
    ) -> Optional[ScanJob]:
        pass
