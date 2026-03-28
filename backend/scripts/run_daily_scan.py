import asyncio
import logging
from app.infrastructure.database import get_engine, async_sessionmaker
from app.adapters.database_repo import EolStatusRepository, OrgRepository, RepoRepository
from app.usecases.scanner import ScanRepositoryUseCase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_daily_scan():
    logger.info("Starting Daily Framework Version Scan...")
    
    engine = get_engine()
    AsyncSessionLocal = async_sessionmaker(
        engine, expire_on_commit=False, autocommit=False, autoflush=False
    )
    
    async with AsyncSessionLocal() as session:
        org_repository = OrgRepository(session)
        organizations = await org_repository.find_all_with_tokens()

        if not organizations:
            logger.info("No organizations found to scan. Exiting.")
            return

        logger.info(
            "Found %s organization(s) to scan: %s",
            len(organizations),
            [org.login for org in organizations],
        )

        # 2. Initialize Repositories and UseCase
        repo_repository = RepoRepository(session)
        eol_status_repository = EolStatusRepository(session)
        scanner_usecase = ScanRepositoryUseCase(repo_repository, eol_status_repository)

        # 3. Execute Scan for each organization
        for org in organizations:
            logger.info("Initiating scan for organization: %s", org.login)
            try:
                statuses = await scanner_usecase.execute(
                    org.login, org.github_access_token
                )
                await session.commit()
                logger.info(
                    "Successfully scanned %s dependency record(s) for %s.",
                    len(statuses),
                    org.login,
                )
            except Exception as e:
                await session.rollback()
                logger.error("Failed to scan organization %s: %s", org.login, str(e))

    logger.info("Daily scan completed successfully.")

if __name__ == "__main__":
    asyncio.run(run_daily_scan())
