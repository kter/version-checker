import boto3
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.infrastructure.config import settings

def get_dsql_auth_token(endpoint: str, region: str = "ap-northeast-1", profile: str = "dev") -> str:
    """Generate an IAM authentication token for connecting to DSQL."""
    session = boto3.Session(profile_name=profile, region_name=region)
    # Using 'dsql' client for IAM token generation.
    # Note: AWS CLI/boto3 integration for DSQL auth token generation depends on the boto3 version.
    # If a specialized method is required by boto3 for DSQL DbConnect, it's typically via generate_db_auth_token
    # or a dedicated DSQL client method.
    client = session.client('dsql')
    
    # generate_db_connect_auth_token is the specific method for DSQL
    token = client.generate_db_connect_auth_token(
        Hostname=endpoint,
        Region=region
    )
    return token

# The username is generally fixed to 'admin' unless we set up IAM mapping to specific Postgres users.
DB_USER = "admin"
DB_NAME = "postgres"  # Default initial database for DSQL

# We must ensure we use an async driver compatible with PostgreSQL such as asyncpg
# SQLAlchemy URL format: postgresql+asyncpg://user:token@endpoint:5432/dbname
def get_database_url() -> str:
    if settings.env == "local":
        endpoint = settings.dsql_endpoint
        token = get_dsql_auth_token(endpoint=endpoint, region=settings.aws_region, profile=settings.aws_profile)
        return f"postgresql+asyncpg://{DB_USER}:{token}@{endpoint}:5432/{DB_NAME}"
    else:
        # In PRD, the ECS task or Lambda role generates the token without profile
        session = boto3.Session(region_name=settings.aws_region)
        client = session.client('dsql')
        token = client.generate_db_connect_auth_token(
            Hostname=settings.dsql_endpoint,
            Region=settings.aws_region
        )
        return f"postgresql+asyncpg://{DB_USER}:{token}@{settings.dsql_endpoint}:5432/{DB_NAME}"

# Given tokens expire (e.g., in 15 mins for standard RDS IAM, similar for DSQL),
# checking/renewing within the engine pooling is important for long-lived applications.
# For simplicity with Aurora serverless, building the engine dynamically limits connection pooling lifecycle,
# but using `pool_pre_ping=True` and an async engine helps in some scenarios.
engine = create_async_engine(
    get_database_url(),
    echo=True, # Set to False in PRD
    pool_pre_ping=True,                     
)

async_session_maker = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

async def get_db_session():
    async with async_session_maker() as session:
        yield session
