from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, DateTime, Boolean
from datetime import datetime
from app.domain.entities import (
    User,
    Repository,
    Organization,
    EolStatus,
    ScanJob,
    TokenUsageEvent,
)

Base = declarative_base()


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    github_id = Column(Integer, nullable=False)
    username = Column(String, nullable=False)
    email = Column(String, nullable=True)
    role = Column(String, default="member")
    github_access_token = Column(String, nullable=True)
    github_refresh_token = Column(String, nullable=True)
    github_access_token_expires_at = Column(DateTime, nullable=True)
    github_refresh_token_expires_at = Column(DateTime, nullable=True)

    def to_domain(self) -> User:
        return User(
            id=self.id,
            github_id=self.github_id,
            username=self.username,
            email=self.email,
            role=self.role,
            github_access_token=self.github_access_token,
            github_refresh_token=self.github_refresh_token,
            github_access_token_expires_at=self.github_access_token_expires_at,
            github_refresh_token_expires_at=self.github_refresh_token_expires_at,
        )


class OrgModel(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True)
    github_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    login = Column(String, nullable=False)
    github_access_token = Column(String, nullable=True)
    token_owner_user_id = Column(String, nullable=True)

    def to_domain(self) -> Organization:
        return Organization(
            id=self.id,
            github_id=self.github_id,
            name=self.name,
            login=self.login,
            github_access_token=self.github_access_token,
            token_owner_user_id=self.token_owner_user_id,
        )


class RepoModel(Base):
    __tablename__ = "repositories"

    id = Column(String, primary_key=True)
    github_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    org_id = Column(String, nullable=True)  # No FK constraint for DSQL
    owner_login = Column(String, nullable=False)
    default_branch = Column(String, default="main")
    is_selected = Column(Boolean, default=True, nullable=False)

    def to_domain(self) -> Repository:
        return Repository(
            id=self.id,
            github_id=self.github_id,
            name=self.name,
            full_name=self.full_name,
            org_id=self.org_id,
            owner_login=self.owner_login,
            default_branch=self.default_branch,
            is_selected=True if self.is_selected is None else self.is_selected,
            updated_at=None,
        )


class EolStatusModel(Base):
    __tablename__ = "eol_statuses"

    id = Column(String, primary_key=True)
    repo_id = Column(String, nullable=False)
    framework_name = Column(String, nullable=False)
    current_version = Column(String, nullable=False)
    eol_date = Column(DateTime, nullable=True)
    is_eol = Column(Boolean, default=False, nullable=False)
    last_scanned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    source_path = Column(String, nullable=True)

    def to_domain(self) -> EolStatus:
        return EolStatus(
            repo_id=self.repo_id,
            framework_name=self.framework_name,
            current_version=self.current_version,
            eol_date=self.eol_date,
            is_eol=self.is_eol,
            last_scanned_at=self.last_scanned_at,
            source_path=self.source_path,
        )


class ScanJobModel(Base):
    __tablename__ = "scan_jobs"

    id = Column(String, primary_key=True)
    org_id = Column(String, nullable=False, index=True)
    requested_by = Column(String, nullable=False)
    status = Column(String, nullable=False)
    total_repos = Column(Integer, default=0, nullable=False)
    completed_repos = Column(Integer, default=0, nullable=False)
    failed_repos = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_domain(self) -> ScanJob:
        return ScanJob(
            id=self.id,
            org_id=self.org_id,
            requested_by=self.requested_by,
            status=self.status,
            total_repos=self.total_repos,
            completed_repos=self.completed_repos,
            failed_repos=self.failed_repos,
            started_at=self.started_at,
            finished_at=self.finished_at,
            error_message=self.error_message,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class TokenUsageEventModel(Base):
    __tablename__ = "token_usage_events"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_domain(self) -> TokenUsageEvent:
        return TokenUsageEvent(
            user_id=self.user_id,
            provider=self.provider,
            model=self.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=self.total_tokens,
            recorded_at=self.recorded_at,
        )
