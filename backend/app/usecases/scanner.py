import asyncio
import base64
import json
import logging
import re
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import httpx

from app.domain.entities import EolStatus, Repository
from app.domain.interfaces import IEolStatusRepository, IRepoRepository

logger = logging.getLogger(__name__)

SCAN_REPOSITORY_CONCURRENCY = 4
SCAN_MANIFEST_CONCURRENCY = 8


class UnsupportedFrameworkError(Exception):
    pass


@dataclass(frozen=True)
class SupportedDependency:
    package_name: str
    product_slug: str
    framework_name: str


SUPPORTED_PACKAGES = {
    "package.json": {
        "nuxt": SupportedDependency("nuxt", "nuxt", "Nuxt"),
        "next": SupportedDependency("next", "nextjs", "Next.js"),
        "react": SupportedDependency("react", "react", "React"),
        "vue": SupportedDependency("vue", "vue", "Vue"),
        "@angular/core": SupportedDependency("@angular/core", "angular", "Angular"),
    },
    "requirements.txt": {
        "django": SupportedDependency("django", "django", "Django"),
    },
    "pyproject.toml": {
        "django": SupportedDependency("django", "django", "Django"),
    },
    "Gemfile": {
        "rails": SupportedDependency("rails", "rails", "Rails"),
    },
    "composer.json": {
        "laravel/framework": SupportedDependency(
            "laravel/framework", "laravel", "Laravel"
        ),
        "symfony/symfony": SupportedDependency("symfony/symfony", "symfony", "Symfony"),
        "symfony/framework-bundle": SupportedDependency(
            "symfony/framework-bundle", "symfony", "Symfony"
        ),
    },
    "pom.xml": {
        "org.springframework.boot": SupportedDependency(
            "org.springframework.boot", "spring-boot", "Spring Boot"
        ),
    },
    "build.gradle": {
        "org.springframework.boot": SupportedDependency(
            "org.springframework.boot", "spring-boot", "Spring Boot"
        ),
    },
    "build.gradle.kts": {
        "org.springframework.boot": SupportedDependency(
            "org.springframework.boot", "spring-boot", "Spring Boot"
        ),
    },
}

RUNTIME_PRODUCTS = {
    "node": SupportedDependency("node", "nodejs", "Node.js"),
    "python": SupportedDependency("python", "python", "Python"),
    "php": SupportedDependency("php", "php", "PHP"),
    "ruby": SupportedDependency("ruby", "ruby", "Ruby"),
    "go": SupportedDependency("go", "go", "Go"),
}

CANDIDATE_MANIFESTS = {
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "go.mod",
    "Cargo.toml",
    "composer.json",
    "Gemfile",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
}


def _extract_version(spec: str) -> Optional[str]:
    match = re.search(r"(\d+(?:\.\d+){0,3})", spec)
    if not match:
        return None
    return match.group(1)


def _version_parts(version: str) -> List[int]:
    return [int(part) for part in re.findall(r"\d+", version)]


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(f"{value}T00:00:00")


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class GitHubClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "GitHubClient":
        self._client = httpx.AsyncClient(timeout=30)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _build_repository(item: Dict[str, Any], owner_login: str) -> Repository:
        return Repository(
            id="",
            github_id=item["id"],
            name=item["name"],
            full_name=item["full_name"],
            org_id=owner_login,
            owner_login=item["owner"]["login"],
            default_branch=item.get("default_branch") or "main",
        )

    async def _request(self, method: str, url: str, **kwargs) -> Any:
        headers = kwargs.pop("headers", {})
        headers.update(
            {
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        if self._client is not None:
            response = await self._client.request(
                method, url, headers=headers, **kwargs
            )
        else:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    async def list_org_repositories(self, org_login: str) -> List[Repository]:
        repositories: List[Repository] = []
        page = 1

        while True:
            payload = await self._request(
                "GET",
                f"https://api.github.com/orgs/{org_login}/repos",
                params={"type": "all", "per_page": 100, "page": page},
            )
            if not payload:
                break

            for item in payload:
                repositories.append(self._build_repository(item, org_login))

            if len(payload) < 100:
                break
            page += 1

        return repositories

    async def list_user_repositories(self, user_login: str) -> List[Repository]:
        repositories: List[Repository] = []
        page = 1

        while True:
            payload = await self._request(
                "GET",
                "https://api.github.com/user/repos",
                params={
                    "affiliation": "owner",
                    "visibility": "all",
                    "per_page": 100,
                    "page": page,
                },
            )
            if not payload:
                break

            for item in payload:
                if item.get("owner", {}).get("login") != user_login:
                    continue
                repositories.append(self._build_repository(item, user_login))

            if len(payload) < 100:
                break
            page += 1

        return repositories

    async def list_manifest_paths(self, repo: Repository) -> List[str]:
        payload = await self._request(
            "GET",
            f"https://api.github.com/repos/{repo.full_name}/git/trees/{repo.default_branch}",
            params={"recursive": 1},
        )
        paths = []
        for item in payload.get("tree", []):
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            if path.split("/")[-1] in CANDIDATE_MANIFESTS:
                paths.append(path)
        return sorted(paths)

    async def fetch_file(self, repo: Repository, path: str) -> Optional[str]:
        payload = await self._request(
            "GET",
            f"https://api.github.com/repos/{repo.full_name}/contents/{path}",
            params={"ref": repo.default_branch},
        )
        if payload.get("encoding") != "base64" or "content" not in payload:
            return None
        return base64.b64decode(payload["content"]).decode("utf-8", errors="ignore")


class EndOfLifeClient:
    def __init__(self):
        self._cache: Dict[str, Optional[Dict[str, Any]]] = {}

    async def get_product(self, product_slug: str) -> Optional[Dict[str, Any]]:
        if product_slug in self._cache:
            return self._cache[product_slug]

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"https://endoflife.date/api/v1/products/{product_slug}/"
            )
        if response.status_code == 404:
            self._cache[product_slug] = None
            return None
        response.raise_for_status()
        payload = response.json().get("result")
        self._cache[product_slug] = payload
        return payload


class FrameworkEolScanner:
    def __init__(self, eol_client: Optional[EndOfLifeClient] = None):
        self.eol_client = eol_client or EndOfLifeClient()

    async def scan_repo(
        self,
        repo: Repository,
        github_access_token: str,
    ) -> List[EolStatus]:
        async with GitHubClient(github_access_token) as github_client:
            manifest_paths = await github_client.list_manifest_paths(repo)
            if not manifest_paths:
                return []

            manifest_semaphore = asyncio.Semaphore(SCAN_MANIFEST_CONCURRENCY)

            async def fetch_manifest(
                path: str,
            ) -> tuple[str, Optional[str]]:
                async with manifest_semaphore:
                    return path, await github_client.fetch_file(repo, path)

            fetched_manifests = await asyncio.gather(
                *(fetch_manifest(path) for path in manifest_paths)
            )

            dependencies: List[tuple[SupportedDependency, str, str]] = []
            for path, content in fetched_manifests:
                if not content:
                    continue
                dependencies.extend(self._extract_dependencies(path, content))

            if not dependencies:
                return []

            async def build_status(
                dependency: tuple[SupportedDependency, str, str],
            ) -> Optional[EolStatus]:
                return await self._build_eol_status(repo, dependency)

            statuses = await asyncio.gather(
                *(build_status(dependency) for dependency in dependencies)
            )

            discovered: Dict[tuple[str, str, Optional[str]], EolStatus] = {}
            for status in statuses:
                if not status:
                    continue
                discovered[
                    (
                        status.framework_name,
                        status.current_version,
                        status.source_path,
                    )
                ] = status

        return list(discovered.values())

    def _extract_dependencies(
        self, path: str, content: str
    ) -> List[tuple[SupportedDependency, str, str]]:
        filename = path.split("/")[-1]
        matches: List[tuple[SupportedDependency, str, str]] = []

        try:
            if filename == "package.json":
                payload = json.loads(content)
                for section in ("dependencies", "devDependencies"):
                    for package_name, spec in payload.get(section, {}).items():
                        dependency = SUPPORTED_PACKAGES["package.json"].get(
                            package_name
                        )
                        version = _extract_version(str(spec))
                        if dependency and version:
                            matches.append((dependency, version, path))

                node_version = _extract_version(
                    str(payload.get("engines", {}).get("node", ""))
                )
                if node_version:
                    matches.append((RUNTIME_PRODUCTS["node"], node_version, path))

            elif filename == "requirements.txt":
                for raw_line in content.splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    package_name = (
                        re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip().lower()
                    )
                    dependency = SUPPORTED_PACKAGES["requirements.txt"].get(
                        package_name
                    )
                    version = _extract_version(line)
                    if dependency and version:
                        matches.append((dependency, version, path))

            elif filename == "pyproject.toml":
                payload = tomllib.loads(content)
                for item in payload.get("project", {}).get("dependencies", []):
                    package_name = (
                        re.split(r"[<>=!~\[]", item, maxsplit=1)[0].strip().lower()
                    )
                    dependency = SUPPORTED_PACKAGES["pyproject.toml"].get(package_name)
                    version = _extract_version(item)
                    if dependency and version:
                        matches.append((dependency, version, path))

                poetry_deps = (
                    payload.get("tool", {}).get("poetry", {}).get("dependencies", {})
                )
                for package_name, spec in poetry_deps.items():
                    if package_name == "python":
                        continue
                    dependency = SUPPORTED_PACKAGES["pyproject.toml"].get(
                        package_name.lower()
                    )
                    version = _extract_version(str(spec))
                    if dependency and version:
                        matches.append((dependency, version, path))

                python_version = _extract_version(
                    str(payload.get("project", {}).get("requires-python", ""))
                ) or _extract_version(str(poetry_deps.get("python", "")))
                if python_version:
                    matches.append((RUNTIME_PRODUCTS["python"], python_version, path))

            elif filename == "go.mod":
                go_match = re.search(r"^go\s+([0-9.]+)$", content, flags=re.MULTILINE)
                if go_match:
                    matches.append((RUNTIME_PRODUCTS["go"], go_match.group(1), path))

            elif filename == "composer.json":
                payload = json.loads(content)
                for section in ("require", "require-dev"):
                    for package_name, spec in payload.get(section, {}).items():
                        dependency = SUPPORTED_PACKAGES["composer.json"].get(
                            package_name
                        )
                        version = _extract_version(str(spec))
                        if dependency and version:
                            matches.append((dependency, version, path))

                php_version = _extract_version(
                    str(payload.get("require", {}).get("php", ""))
                )
                if php_version:
                    matches.append((RUNTIME_PRODUCTS["php"], php_version, path))

            elif filename == "Gemfile":
                for match in re.finditer(
                    r"gem\s+['\"](?P<name>[^'\"]+)['\"](?:\s*,\s*['\"](?P<version>[^'\"]+)['\"])?",
                    content,
                ):
                    dependency = SUPPORTED_PACKAGES["Gemfile"].get(match.group("name"))
                    version = _extract_version(match.group("version") or "")
                    if dependency and version:
                        matches.append((dependency, version, path))

                ruby_match = re.search(
                    r"ruby\s+['\"](?P<version>[^'\"]+)['\"]", content
                )
                if ruby_match:
                    version = _extract_version(ruby_match.group("version"))
                    if version:
                        matches.append((RUNTIME_PRODUCTS["ruby"], version, path))

            elif filename == "pom.xml":
                root = ET.fromstring(content)
                spring_version = None
                for child in list(root):
                    if child.tag.split("}")[-1] != "parent":
                        continue

                    artifact_id = None
                    version_text = None
                    group_id = None
                    for parent_child in list(child):
                        tag = parent_child.tag.split("}")[-1]
                        if tag == "groupId":
                            group_id = parent_child.text
                        elif tag == "artifactId":
                            artifact_id = parent_child.text
                        elif tag == "version":
                            version_text = parent_child.text

                    if (
                        group_id == "org.springframework.boot"
                        and artifact_id == "spring-boot-starter-parent"
                    ):
                        spring_version = _extract_version(version_text or "")
                        break

                if spring_version:
                    matches.append(
                        (
                            SUPPORTED_PACKAGES["pom.xml"]["org.springframework.boot"],
                            spring_version,
                            path,
                        )
                    )

            elif filename in {"build.gradle", "build.gradle.kts"}:
                spring_match = re.search(
                    r"org\.springframework\.boot[\"']?\s+version\s+[\"']([0-9][^\"']*)[\"']",
                    content,
                ) or re.search(r"spring-boot[^:\"']*[:\"]([0-9][^\"'\s)]*)", content)
                if spring_match:
                    version = _extract_version(spring_match.group(1))
                    if version:
                        matches.append(
                            (
                                SUPPORTED_PACKAGES[filename][
                                    "org.springframework.boot"
                                ],
                                version,
                                path,
                            )
                        )
        except (ET.ParseError, json.JSONDecodeError, tomllib.TOMLDecodeError):
            return []

        return matches

    async def _build_eol_status(
        self,
        repo: Repository,
        dependency: tuple[SupportedDependency, str, str],
    ) -> Optional[EolStatus]:
        supported, current_version, source_path = dependency
        product = await self.eol_client.get_product(supported.product_slug)
        if not product:
            return None

        release = self._match_release(product.get("releases", []), current_version)
        if not release:
            return None

        return EolStatus(
            repo_id=repo.id,
            framework_name=supported.framework_name,
            current_version=current_version,
            is_eol=bool(release.get("isEol")),
            eol_date=_parse_date(release.get("eolFrom")),
            last_scanned_at=_utcnow_naive(),
            source_path=source_path,
        )

    def _match_release(
        self, releases: List[Dict[str, Any]], current_version: str
    ) -> Optional[Dict[str, Any]]:
        current_parts = _version_parts(current_version)
        if not current_parts:
            return None

        candidates: List[tuple[int, Dict[str, Any]]] = []
        for release in releases:
            name = release.get("name")
            if not name:
                continue
            release_parts = _version_parts(str(name))
            if not release_parts:
                continue
            if current_parts[: len(release_parts)] == release_parts:
                candidates.append((len(release_parts), release))

        if not candidates:
            for release in releases:
                release_parts = _version_parts(str(release.get("name", "")))
                if release_parts and release_parts[0] == current_parts[0]:
                    candidates.append((1, release))

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: (
                item[0],
                _parse_date(item[1].get("releaseDate")) or datetime.min,
            ),
            reverse=True,
        )
        return candidates[0][1]


class ScanRepositoryUseCase:
    def __init__(
        self,
        repo_repository: IRepoRepository,
        eol_status_repository: IEolStatusRepository,
        scanner: Optional[FrameworkEolScanner] = None,
    ):
        self.repo_repository = repo_repository
        self.eol_status_repository = eol_status_repository
        self.scanner = scanner or FrameworkEolScanner()

    async def get_saved_results(self, org_id: str) -> List[EolStatus]:
        return await self.eol_status_repository.find_by_org(org_id)

    async def list_repositories(
        self, org_id: str, github_access_token: str, user_login: str
    ) -> List[Repository]:
        saved_repositories = await self.repo_repository.find_by_org(org_id)
        if saved_repositories:
            return saved_repositories

        github_client = GitHubClient(github_access_token)
        if org_id == user_login:
            repositories = await github_client.list_user_repositories(user_login)
        else:
            repositories = await github_client.list_org_repositories(org_id)

        persisted_repositories: List[Repository] = []
        for repo in repositories:
            persisted_repositories.append(await self.repo_repository.save(repo))

        return persisted_repositories

    async def execute(
        self, org_id: str, github_access_token: str, user_login: str
    ) -> List[EolStatus]:
        saved_repositories = await self.list_repositories(
            org_id, github_access_token, user_login
        )
        if not saved_repositories:
            return []

        repository_semaphore = asyncio.Semaphore(SCAN_REPOSITORY_CONCURRENCY)

        async def scan_repository(repo: Repository) -> List[EolStatus]:
            async with repository_semaphore:
                try:
                    statuses = await self.scanner.scan_repo(repo, github_access_token)
                    await self.eol_status_repository.replace_for_repo(repo.id, statuses)
                    return statuses
                except Exception:
                    logger.exception("Failed to scan repository %s", repo.full_name)
                    return []

        results = await asyncio.gather(
            *(scan_repository(repo) for repo in saved_repositories)
        )
        return [status for statuses in results for status in statuses]
