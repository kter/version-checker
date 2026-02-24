import asyncio
import logging
from sqlalchemy import select
from app.infrastructure.database import get_engine, async_sessionmaker
from app.adapters.models import RepoModel
from app.adapters.database_repo import RepoRepository
from app.adapters.dynamo_repo import DynamoEolCacheRepository
from app.usecases.scanner import ScanRepositoryUseCase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_daily_scan():
    logger.info("Starting Daily Framework Version Scan...")
    
    engine = await get_engine()
    AsyncSessionLocal = async_sessionmaker(
        engine, expire_on_commit=False, autocommit=False, autoflush=False
    )
    
    async with AsyncSessionLocal() as session:
        # 1. Identify all unique organizations that have registered repositories
        logger.info("Fetching unique organizations from registered repositories...")
        result = await session.execute(select(RepoModel.org_id).distinct())
        org_ids = [row[0] for row in result.all() if row[0]]
        
        if not org_ids:
            logger.info("No organizations found to scan. Exiting.")
            return

        logger.info(f"Found {len(org_ids)} organization(s) to scan: {org_ids}")

        # 2. Initialize Repositories and UseCase
        repo_repository = RepoRepository(session)
        cache_repository = DynamoEolCacheRepository()
        scanner_usecase = ScanRepositoryUseCase(repo_repository, cache_repository)

        # 3. Execute Scan for each organization
        for org_id in org_ids:
            logger.info(f"Initiating scan for organization: {org_id}")
            try:
                # Execute handles fetching repos, checking cache, scanning, and updating DynamoDB
                statuses = await scanner_usecase.execute(org_id)
                logger.info(f"Successfully scanned {len(statuses)} repositories for {org_id}.")
            except Exception as e:
                logger.error(f"Failed to scan organization {org_id}: {str(e)}")

    logger.info("Daily scan completed successfully.")

if __name__ == "__main__":
    asyncio.run(run_daily_scan())
