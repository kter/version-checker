import asyncio
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

    await ensure_repo_selection_column()
    await ensure_user_github_token_columns()
    await ensure_organization_token_owner_column()


async def ensure_repo_selection_column():
    engine = get_engine()

    async with engine.connect() as conn:
        existing_tables = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
    if "repositories" not in existing_tables:
        return

    async with engine.connect() as conn:
        existing_columns = await conn.run_sync(
            lambda sync_conn: [
                column["name"]
                for column in inspect(sync_conn).get_columns("repositories")
            ]
        )
    if "is_selected" in existing_columns:
        return

    async with engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE repositories " "ADD COLUMN is_selected BOOLEAN")
        )
        await conn.execute(
            text(
                "UPDATE repositories "
                "SET is_selected = TRUE "
                "WHERE is_selected IS NULL"
            )
        )
    logger.info("Added repositories.is_selected column")


async def _get_existing_columns(table_name: str) -> list[str]:
    engine = get_engine()

    async with engine.connect() as conn:
        existing_tables = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
    if table_name not in existing_tables:
        return []

    async with engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: [
                column["name"] for column in inspect(sync_conn).get_columns(table_name)
            ]
        )


async def ensure_user_github_token_columns():
    engine = get_engine()
    existing_columns = await _get_existing_columns("users")
    if not existing_columns:
        return

    missing_columns = {
        "github_access_token": "ALTER TABLE users ADD COLUMN github_access_token VARCHAR",
        "github_refresh_token": "ALTER TABLE users ADD COLUMN github_refresh_token VARCHAR",
        "github_access_token_expires_at": (
            "ALTER TABLE users ADD COLUMN github_access_token_expires_at TIMESTAMP"
        ),
        "github_refresh_token_expires_at": (
            "ALTER TABLE users ADD COLUMN github_refresh_token_expires_at TIMESTAMP"
        ),
    }

    for column_name, statement in missing_columns.items():
        if column_name in existing_columns:
            continue
        async with engine.begin() as conn:
            await conn.execute(text(statement))
        logger.info("Added users.%s column", column_name)


async def ensure_organization_token_owner_column():
    engine = get_engine()
    existing_columns = await _get_existing_columns("organizations")
    if not existing_columns or "token_owner_user_id" in existing_columns:
        return

    async with engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE organizations " "ADD COLUMN token_owner_user_id VARCHAR")
        )
    logger.info("Added organizations.token_owner_user_id column")


if __name__ == "__main__":
    asyncio.run(init_db())
