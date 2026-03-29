from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_ENV_FILES = (
    str(REPO_ROOT / ".env"),
    str(BACKEND_DIR / ".env"),
)


class Settings(BaseSettings):
    env: str = "local"
    aws_profile: str = "dev"
    aws_region: str = "ap-northeast-1"

    dsql_endpoint: str = ""
    dynamo_table: str = ""
    scan_queue_url: str = ""

    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None
    frontend_base_url: str = "http://localhost:3000"
    cors_allow_origins: str = "http://localhost:3000"

    @property
    def dsql_hostname(self) -> str:
        """Extract hostname from DSQL ARN or return as-is if already a hostname."""
        endpoint = self.dsql_endpoint
        if endpoint.startswith("arn:aws:dsql:"):
            # arn:aws:dsql:ap-northeast-1:123456789012:cluster/CLUSTER_ID
            parts = endpoint.split("/")
            if len(parts) >= 2:
                cluster_id = parts[-1]
                region = endpoint.split(":")[3]
                return f"{cluster_id}.dsql.{region}.on.aws"
        return endpoint

    @property
    def github_redirect_uri(self) -> str:
        return f"{self.frontend_base_url.rstrip('/')}/auth/callback"

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allow_origins.split(",")
            if origin.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILES,
        extra="allow",
    )


settings = Settings()
