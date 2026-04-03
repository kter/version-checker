import asyncio
import json
import logging
from typing import Any, Dict

from app.adapters.database_repo import (
    EolStatusRepository,
    OrgRepository,
    RepoRepository,
    ScanJobRepository,
    UserRepository,
)
from app.adapters.dynamo_repo import DynamoRepoListCacheRepository
from app.adapters.sqs_scan_queue import SqsScanQueue
from app.infrastructure.database import get_session_maker
from app.usecases.scan_jobs import ScanJobWorkerService
from app.usecases.scanner import ScanRepositoryUseCase

logger = logging.getLogger(__name__)


async def _process_record(record: Dict[str, Any]) -> None:
    payload = json.loads(record["body"])
    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            org_repository = OrgRepository(session)
            user_repository = UserRepository(session)
            repo_repository = RepoRepository(session)
            eol_status_repository = EolStatusRepository(session)
            scan_job_repository = ScanJobRepository(session)
            queue = SqsScanQueue()
            repo_cache_repository = DynamoRepoListCacheRepository()
            scan_usecase = ScanRepositoryUseCase(
                repo_repository,
                eol_status_repository,
                repo_cache_repository=repo_cache_repository,
            )
            worker = ScanJobWorkerService(
                org_repository,
                user_repository,
                repo_repository,
                eol_status_repository,
                scan_job_repository,
                queue,
                scanner_usecase=scan_usecase,
            )
            await worker.process_message(payload)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Failed to process scan queue message")


def lambda_handler(event, context):
    for record in event.get("Records", []):
        asyncio.run(_process_record(record))
    return {"statusCode": 200}
