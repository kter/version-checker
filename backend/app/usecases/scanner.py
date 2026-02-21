from typing import List, Optional
from datetime import datetime
from app.domain.interfaces import IEolCacheRepository, IRepoRepository
from app.domain.entities import Repository, EolStatus

class UnsupportedFrameworkError(Exception):
    pass

class FrameworkEolScanner:
    """Simulates scanning a repository to determine framework versions."""

    async def scan_repo(self, repo: Repository) -> List[EolStatus]:
        # Provide Mocked implementation for initial version
        # It should scan package.json, requirements.txt, pyproject.toml, etc. via Github API.
        
        # Simulating that we found a specific framework in the repo.
        simulate_framework_found = "nuxt"
        simulate_version_found = "2.15.8"
        
        # Hardcoding the EOL verification for the simulation
        # EOL checking should ideally happen via API like https://endoflife.date/api
        is_eol = False
        eol_date = None
        
        if simulate_framework_found == "nuxt" and simulate_version_found.startswith("2."):
            is_eol = True
            eol_date = datetime(2023, 12, 31)

        return [
            EolStatus(
                repo_id=repo.id,
                framework_name=simulate_framework_found,
                current_version=simulate_version_found,
                is_eol=is_eol,
                eol_date=eol_date
            )
        ]

class ScanRepositoryUseCase:
    def __init__(self, repo_repository: IRepoRepository, cache_repository: IEolCacheRepository):
        self.repo_repository = repo_repository
        self.cache_repository = cache_repository
        self.scanner = FrameworkEolScanner()

    async def execute(self, org_id: str) -> List[EolStatus]:
        repos = await self.repo_repository.find_by_org(org_id)
        all_statuses = []

        for repo in repos:
            # First check Cache
            cached_statuses = await self.cache_repository.get_eol_status(repo.id)
            if cached_statuses:
                all_statuses.extend(cached_statuses)
                continue
            
            # Cache miss, perform scan
            statuses = await self.scanner.scan_repo(repo)
            
            # Save to Cache
            for status in statuses:
                await self.cache_repository.set_eol_status(status)
            
            all_statuses.extend(statuses)

        return all_statuses
