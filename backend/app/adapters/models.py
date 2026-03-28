from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, DateTime, Boolean
from datetime import datetime
from app.domain.entities import User, Repository, Organization, EolStatus

Base = declarative_base()


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    github_id = Column(Integer, nullable=False)
    username = Column(String, nullable=False)
    email = Column(String, nullable=True)
    role = Column(String, default="member")

    def to_domain(self) -> User:
        return User(
            id=self.id,
            github_id=self.github_id,
            username=self.username,
            email=self.email,
            role=self.role,
        )


class OrgModel(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True)
    github_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    login = Column(String, nullable=False)
    github_access_token = Column(String, nullable=True)

    def to_domain(self) -> Organization:
        return Organization(
            id=self.id,
            github_id=self.github_id,
            name=self.name,
            login=self.login,
            github_access_token=self.github_access_token,
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

    def to_domain(self) -> Repository:
        return Repository(
            id=self.id,
            github_id=self.github_id,
            name=self.name,
            full_name=self.full_name,
            org_id=self.org_id,
            owner_login=self.owner_login,
            default_branch=self.default_branch,
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
