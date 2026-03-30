from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Optional, List

SCAN_JOB_STATUS_QUEUED = "queued"
SCAN_JOB_STATUS_RUNNING = "running"
SCAN_JOB_STATUS_COMPLETED = "completed"
SCAN_JOB_STATUS_PARTIAL_FAILED = "partial_failed"
SCAN_JOB_STATUS_FAILED = "failed"

ACTIVE_SCAN_JOB_STATUSES = {
    SCAN_JOB_STATUS_QUEUED,
    SCAN_JOB_STATUS_RUNNING,
}


@dataclass
class Organization:
    id: str
    github_id: int
    name: str
    login: str
    github_access_token: Optional[str] = None
    token_owner_user_id: Optional[str] = None


@dataclass
class User:
    id: str
    github_id: int
    username: str
    email: Optional[str] = None
    role: str = "member"  # Simple RBAC
    organizations: List[Organization] = field(default_factory=list)
    github_access_token: Optional[str] = None
    github_refresh_token: Optional[str] = None
    github_access_token_expires_at: Optional[datetime] = None
    github_refresh_token_expires_at: Optional[datetime] = None


@dataclass
class Repository:
    id: str
    github_id: int
    name: str
    full_name: str
    org_id: Optional[str] = None
    owner_login: str = ""
    default_branch: str = "main"
    is_selected: bool = True


@dataclass
class EolStatus:
    repo_id: str
    framework_name: str
    current_version: str
    eol_date: Optional[datetime] = None
    is_eol: bool = False
    last_scanned_at: datetime = field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    source_path: Optional[str] = None


@dataclass
class ScanJob:
    id: str
    org_id: str
    requested_by: str
    status: str = SCAN_JOB_STATUS_QUEUED
    total_repos: int = 0
    completed_repos: int = 0
    failed_repos: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None)
    )


@dataclass
class TokenUsageEvent:
    user_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    recorded_at: datetime = field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
