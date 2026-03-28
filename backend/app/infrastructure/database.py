import boto3
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.infrastructure.config import settings


def get_dsql_auth_token(
    hostname: str, region: str = "ap-northeast-1", profile: str = "dev"
) -> str:
    """Generate an IAM authentication token for connecting to DSQL as admin."""
    session = boto3.Session(profile_name=profile, region_name=region)
    client = session.client("dsql", region_name=region)
    # admin user requires DbConnectAdmin action token
    token = client.generate_db_connect_admin_auth_token(
        Hostname=hostname, Region=region
    )
    return token


DB_USER = "admin"
DB_NAME = "postgres"


def get_database_url() -> str:
    hostname = settings.dsql_hostname
    if settings.env == "local":
        token = get_dsql_auth_token(
            hostname=hostname, region=settings.aws_region, profile=settings.aws_profile
        )
    else:
        session = boto3.Session(region_name=settings.aws_region)
        client = session.client("dsql", region_name=settings.aws_region)
        token = client.generate_db_connect_admin_auth_token(
            Hostname=hostname, Region=settings.aws_region
        )
    return (
        f"postgresql+asyncpg://{DB_USER}:{token}@{hostname}:5432/{DB_NAME}?ssl=require"
    )


# Lazy engine initialization to avoid startup crash
_engine = None
_async_session_maker = None


from sqlalchemy import event


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_database_url(),
            echo=(settings.env != "prd"),
            pool_pre_ping=True,
            isolation_level="AUTOCOMMIT",
        )

        @event.listens_for(_engine.sync_engine, "do_connect")
        def provide_token(dialect, conn_rec, cargs, cparams):
            hostname = settings.dsql_hostname
            if settings.env == "local":
                token = get_dsql_auth_token(
                    hostname=hostname,
                    region=settings.aws_region,
                    profile=settings.aws_profile,
                )
            else:
                session = boto3.Session(region_name=settings.aws_region)
                client = session.client("dsql", region_name=settings.aws_region)
                token = client.generate_db_connect_admin_auth_token(
                    Hostname=hostname, Region=settings.aws_region
                )
            cparams["password"] = token

    return _engine


def get_session_maker():
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _async_session_maker


async def get_db_session():
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
