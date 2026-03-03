from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AuthConfig:
    type: str
    token: Optional[str] = None

    def inject_into_url(self, url: str) -> str:
        if self.type == "oauth2" and self.token:
            if "://" in url:
                scheme, rest = url.split("://", 1)
            else:
                scheme, rest = "https", url
            return f"{scheme}://oauth2:{self.token}@{rest}"
        return url


@dataclass
class GitEndpoint:
    url: str
    proxy: Optional[str]
    auth: AuthConfig

    @property
    def authed_url(self) -> str:
        return self.auth.inject_into_url(self.url)


@dataclass
class RepoConfig:
    name: str
    dst_override: Optional[str] = None
    include_branches: List[str] = field(default_factory=list)
    exclude_branches: List[str] = field(default_factory=list)
    sync_tags: bool = False

    @property
    def path(self) -> str:
        return self.name.rsplit("/", 1)[0] if "/" in self.name else ""

    @property
    def repo_name(self) -> str:
        return self.name.rsplit("/", 1)[-1]


@dataclass
class SyncConfig:
    src: GitEndpoint
    dst: GitEndpoint
    repos: List[RepoConfig]
    temp_dir: str = "/tmp/git-sync"
    sleep_seconds: int = 600
    allow_force_push: bool = False
