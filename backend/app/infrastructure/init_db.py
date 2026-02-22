import logging
from sqlalchemy import text, inspect
from app.adapters.models import Base
from app.infrastructure.database import get_engine

logger = logging.getLogger(__name__)


async def init_db():
    """Create tables one at a time — DSQL only allows one DDL per transaction."""
    engine = get_engine()

    # Get list of existing tables
    async with engine.connect() as conn:
        existing = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )

    # Create each table individually in its own transaction
    for table in Base.metadata.sorted_tables:
        if table.name in existing:
            logger.info(f"Table '{table.name}' already exists, skipping")
            continue
        try:
            async with engine.begin() as conn:
                await conn.run_sync(table.create)
            logger.info(f"Created table '{table.name}'")
        except Exception as e:
            logger.warning(f"Failed to create table '{table.name}': {e}")
