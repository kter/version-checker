import asyncio
import base64
import json
import logging
import re
import shlex
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import httpx

from app.domain.entities import EolStatus, Repository
from app.domain.interfaces import (
    IEolStatusRepository,
    IRepoListCacheRepository,
    IRepoRepository,
)

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

DOCKER_RUNTIME_IMAGES = {
    "node": RUNTIME_PRODUCTS["node"],
    "python": RUNTIME_PRODUCTS["python"],
    "php": RUNTIME_PRODUCTS["php"],
    "ruby": RUNTIME_PRODUCTS["ruby"],
    "go": RUNTIME_PRODUCTS["go"],
    "golang": RUNTIME_PRODUCTS["go"],
}

DOCKER_OS_PRODUCTS = {
    "alpine": SupportedDependency("alpine", "alpine-linux", "Alpine Linux"),
    "debian": SupportedDependency("debian", "debian", "Debian"),
    "ubuntu": SupportedDependency("ubuntu", "ubuntu", "Ubuntu"),
}

DEBIAN_CODENAMES = {
    "bookworm",
    "bullseye",
    "buster",
    "stretch",
    "jessie",
    "wheezy",
    "squeeze",
    "lenny",
    "etch",
    "trixie",
    "forky",
    "sid",
}

UBUNTU_CODENAMES = {
    "noble",
    "jammy",
    "focal",
    "bionic",
    "xenial",
    "mantic",
    "lunar",
    "kinetic",
    "impish",
    "hirsute",
    "groovy",
    "focal",
    "eoan",
    "disco",
    "cosmic",
    "bionic",
    "artful",
    "zesty",
    "yakkety",
    "xenial",
}

DOCKER_VARIABLE_PATTERN = re.compile(
    r"\$(?:\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)\}|(?P<plain>[A-Za-z_][A-Za-z0-9_]*))"
)


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


def _is_candidate_manifest_path(path: str) -> bool:
    filename = path.split("/")[-1]
    return filename in CANDIDATE_MANIFESTS or filename.startswith("Dockerfile")


def _normalize_cycle_text(value: Optional[str]) -> str:
    return str(value or "").strip().lower()


def _dockerfile_lines(content: str) -> List[str]:
    logical_lines: List[str] = []
    buffer: List[str] = []

    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not buffer and (not stripped or stripped.startswith("#")):
            continue

        continued = raw_line.rstrip().endswith("\\")
        line = raw_line.rstrip()
        if continued:
            line = line[:-1]
        buffer.append(line.strip())

        if continued:
            continue

        logical_line = " ".join(part for part in buffer if part)
        if logical_line and not logical_line.startswith("#"):
            logical_lines.append(logical_line)
        buffer = []

    if buffer:
        logical_line = " ".join(part for part in buffer if part)
        if logical_line and not logical_line.startswith("#"):
            logical_lines.append(logical_line)

    return logical_lines


def _substitute_docker_args(value: str, defaults: Dict[str, str]) -> Optional[str]:
    def replace(match: re.Match[str]) -> str:
        key = match.group("braced") or match.group("plain") or ""
        return defaults.get(key, match.group(0))

    substituted = DOCKER_VARIABLE_PATTERN.sub(replace, value)
    if "$" in substituted:
        return None
    return substituted


def _split_docker_image_reference(image_reference: str) -> tuple[str, Optional[str]]:
    without_digest = image_reference.split("@", 1)[0]
    image_name = without_digest.rsplit("/", 1)[-1]
    if ":" in image_name:
        name, tag = image_name.rsplit(":", 1)
        return name.lower(), tag
    return image_name.lower(), None


def _extract_direct_os_cycle(tag: Optional[str], codenames: set[str]) -> Optional[str]:
    if not tag:
        return None

    primary_token = _normalize_cycle_text(tag).split("-", 1)[0]
    version = _extract_version(primary_token)
    if version:
        return version
    if primary_token in codenames:
        return primary_token
    return None


def _extract_debian_cycle_from_tag(tag: Optional[str]) -> Optional[str]:
    if not tag:
        return None
    for token in re.split(r"[-_.]", _normalize_cycle_text(tag)):
        if token in DEBIAN_CODENAMES:
            return token
    return None


def _extract_ubuntu_cycle_from_tag(tag: Optional[str]) -> Optional[str]:
    if not tag:
        return None
    for token in re.split(r"[-_.]", _normalize_cycle_text(tag)):
        if token in UBUNTU_CODENAMES:
            return token
    return None


def _extract_alpine_cycle_from_tag(tag: Optional[str]) -> Optional[str]:
    if not tag:
        return None

    alpine_match = re.search(
        r"(?:^|[-_.])alpine(?P<version>\d+(?:\.\d+)*)",
        _normalize_cycle_text(tag),
    )
    if not alpine_match:
        return None
    return alpine_match.group("version")


def _extract_direct_alpine_cycle(tag: Optional[str]) -> Optional[str]:
    if not tag:
        return None
    primary_token = _normalize_cycle_text(tag).split("-", 1)[0]
    return _extract_version(primary_token)


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
            if _is_candidate_manifest_path(path):
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
            elif filename.startswith("Dockerfile"):
                matches.extend(self._extract_docker_dependencies(path, content))
        except (ET.ParseError, json.JSONDecodeError, tomllib.TOMLDecodeError):
            return []

        return matches

    def _extract_docker_dependencies(
        self, path: str, content: str
    ) -> List[tuple[SupportedDependency, str, str]]:
        matches: List[tuple[SupportedDependency, str, str]] = []
        arg_defaults: Dict[str, str] = {}

        for line in _dockerfile_lines(content):
            upper_line = line.upper()
            if upper_line.startswith("ARG "):
                name, value = self._parse_arg_instruction(line)
                if name and value is not None:
                    resolved_value = _substitute_docker_args(value, arg_defaults)
                    if resolved_value is not None:
                        arg_defaults[name] = resolved_value
                continue

            if not upper_line.startswith("FROM "):
                continue

            image_reference = self._parse_from_instruction(line, arg_defaults)
            if not image_reference:
                continue

            matches.extend(
                self._extract_docker_image_dependencies(path, image_reference)
            )

        return matches

    def _parse_arg_instruction(self, line: str) -> tuple[Optional[str], Optional[str]]:
        try:
            tokens = shlex.split(line, comments=False)
        except ValueError:
            return None, None

        if len(tokens) < 2 or tokens[0].upper() != "ARG":
            return None, None

        declaration = tokens[1]
        if "=" not in declaration:
            return declaration, None

        name, value = declaration.split("=", 1)
        return name, value

    def _parse_from_instruction(
        self,
        line: str,
        arg_defaults: Dict[str, str],
    ) -> Optional[str]:
        try:
            tokens = shlex.split(line, comments=False)
        except ValueError:
            return None

        if len(tokens) < 2 or tokens[0].upper() != "FROM":
            return None

        image_reference: Optional[str] = None
        for token in tokens[1:]:
            if token.startswith("--"):
                continue
            if token.upper() == "AS":
                break
            image_reference = token
            break

        if not image_reference:
            return None

        return _substitute_docker_args(image_reference, arg_defaults)

    def _extract_docker_image_dependencies(
        self,
        path: str,
        image_reference: str,
    ) -> List[tuple[SupportedDependency, str, str]]:
        matches: List[tuple[SupportedDependency, str, str]] = []
        image_name, tag = _split_docker_image_reference(image_reference)

        runtime_dependency = DOCKER_RUNTIME_IMAGES.get(image_name)
        if runtime_dependency and tag:
            runtime_version = _extract_version(tag)
            if runtime_version:
                matches.append((runtime_dependency, runtime_version, path))

            if image_name in {"node", "python", "php", "ruby", "go", "golang"}:
                os_dependency = self._extract_runtime_base_os_dependency(path, tag)
                if os_dependency:
                    matches.append(os_dependency)

        direct_os_dependency = self._extract_direct_os_dependency(path, image_name, tag)
        if direct_os_dependency:
            matches.append(direct_os_dependency)

        return matches

    def _extract_runtime_base_os_dependency(
        self,
        path: str,
        tag: str,
    ) -> Optional[tuple[SupportedDependency, str, str]]:
        alpine_cycle = _extract_alpine_cycle_from_tag(tag)
        if alpine_cycle:
            return (DOCKER_OS_PRODUCTS["alpine"], alpine_cycle, path)

        debian_cycle = _extract_debian_cycle_from_tag(tag)
        if debian_cycle:
            return (DOCKER_OS_PRODUCTS["debian"], debian_cycle, path)

        ubuntu_cycle = _extract_ubuntu_cycle_from_tag(tag)
        if ubuntu_cycle:
            return (DOCKER_OS_PRODUCTS["ubuntu"], ubuntu_cycle, path)

        return None

    def _extract_direct_os_dependency(
        self,
        path: str,
        image_name: str,
        tag: Optional[str],
    ) -> Optional[tuple[SupportedDependency, str, str]]:
        if image_name == "alpine":
            cycle = _extract_direct_alpine_cycle(tag)
            if cycle:
                return (DOCKER_OS_PRODUCTS["alpine"], cycle, path)

        if image_name == "debian":
            cycle = _extract_direct_os_cycle(tag, DEBIAN_CODENAMES)
            if cycle:
                return (DOCKER_OS_PRODUCTS["debian"], cycle, path)

        if image_name == "ubuntu":
            cycle = _extract_direct_os_cycle(tag, UBUNTU_CODENAMES)
            if cycle:
                return (DOCKER_OS_PRODUCTS["ubuntu"], cycle, path)

        return None

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
        normalized_current = _normalize_cycle_text(current_version)
        exact_candidates = [
            release
            for release in releases
            if normalized_current
            and normalized_current
            in {
                _normalize_cycle_text(release.get("name")),
                _normalize_cycle_text(release.get("codename")),
            }
        ]
        if exact_candidates:
            exact_candidates.sort(
                key=lambda release: _parse_date(release.get("releaseDate"))
                or datetime.min,
                reverse=True,
            )
            return exact_candidates[0]

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
        repo_cache_repository: Optional[IRepoListCacheRepository] = None,
    ):
        self.repo_repository = repo_repository
        self.eol_status_repository = eol_status_repository
        self.scanner = scanner or FrameworkEolScanner()
        self.repo_cache_repository = repo_cache_repository

    async def get_saved_results(self, org_id: str) -> List[EolStatus]:
        return await self.eol_status_repository.find_by_org(org_id)

    async def list_repositories(
        self,
        org_id: str,
        github_access_token: str,
        user_login: str,
        use_cache: bool = False,
    ) -> List[Repository]:
        saved_repositories = await self.repo_repository.find_by_org(org_id)
        saved_by_github_id = {repo.github_id: repo for repo in saved_repositories}

        repositories = None
        if use_cache and self.repo_cache_repository:
            repositories = await self.repo_cache_repository.get_repositories(org_id)

        if repositories is None:
            github_client = GitHubClient(github_access_token)
            if org_id == user_login:
                repositories = await github_client.list_user_repositories(user_login)
            else:
                repositories = await github_client.list_org_repositories(org_id)
            if self.repo_cache_repository:
                await self.repo_cache_repository.set_repositories(org_id, repositories)

        persisted_repositories: List[Repository] = []
        for repo in repositories:
            existing = saved_by_github_id.get(repo.github_id)
            if existing:
                repo.id = existing.id
                repo.is_selected = existing.is_selected
                if _repositories_match(existing, repo):
                    persisted_repositories.append(existing)
                    continue
            else:
                repo.is_selected = False
            persisted_repositories.append(await self.repo_repository.save(repo))

        return persisted_repositories

    async def execute(
        self, org_id: str, github_access_token: str, user_login: str
    ) -> List[EolStatus]:
        saved_repositories = await self.list_repositories(
            org_id, github_access_token, user_login
        )
        selected_repositories = [
            repo for repo in saved_repositories if repo.is_selected
        ]
        if not selected_repositories:
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
            *(scan_repository(repo) for repo in selected_repositories)
        )
        return [status for statuses in results for status in statuses]


def _repositories_match(existing: Repository, candidate: Repository) -> bool:
    return (
        existing.github_id == candidate.github_id
        and existing.name == candidate.name
        and existing.full_name == candidate.full_name
        and existing.org_id == candidate.org_id
        and existing.owner_login == candidate.owner_login
        and existing.default_branch == candidate.default_branch
        and existing.is_selected == candidate.is_selected
    )
