import asyncio
import logging
from app.infrastructure.database import get_engine, async_sessionmaker
from app.adapters.database_repo import (
    OrgRepository,
    RepoRepository,
    EolStatusRepository,
    ScanJobRepository,
)
from app.adapters.sqs_scan_queue import SqsScanQueue
from app.usecases.scan_jobs import ScanJobService
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
        scan_job_repository = ScanJobRepository(session)
        queue = SqsScanQueue()
        scanner_usecase = ScanRepositoryUseCase(repo_repository, eol_status_repository)
        scan_job_service = ScanJobService(
            org_repository,
            repo_repository,
            eol_status_repository,
            scan_job_repository,
            queue,
            scanner_usecase=scanner_usecase,
        )

        # 3. Execute Scan for each organization
        for org in organizations:
            logger.info("Queueing scan for organization: %s", org.login)
            try:
                job = await scan_job_service.enqueue_scan(org.login, org.login)
                await session.commit()
                logger.info(
                    "Queued scan job %s for %s.",
                    job.id,
                    org.login,
                )
            except Exception as e:
                await session.rollback()
                logger.error("Failed to queue organization %s: %s", org.login, str(e))

    logger.info("Daily scan completed successfully.")


if __name__ == "__main__":
    asyncio.run(run_daily_scan())
