from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Optional, List


@dataclass
class Organization:
    id: str
    github_id: int
    name: str
    login: str
    github_access_token: Optional[str] = None


@dataclass
class User:
    id: str
    github_id: int
    username: str
    email: Optional[str] = None
    role: str = "member"  # Simple RBAC
    organizations: List[Organization] = field(default_factory=list)
    github_access_token: Optional[str] = None


@dataclass
class Repository:
    id: str
    github_id: int
    name: str
    full_name: str
    org_id: Optional[str] = None
    owner_login: str = ""
    default_branch: str = "main"


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
