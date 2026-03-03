import yaml
from pathlib import Path
from core.models import SyncConfig, GitEndpoint, RepoConfig, AuthConfig


def _parse_auth(raw_auth: dict) -> AuthConfig:
    """
    Создаёт AuthConfig из секции auth конфига.

    Поддерживаемые типы:
        none   — без авторизации (токен игнорируется)
        oauth2 — токен встраивается в URL

    Если секция auth отсутствует — возвращает AuthConfig(type="none").
    """
    return AuthConfig(
        type=raw_auth.get("type", "none"),
        token=raw_auth.get("token")
    )


def _parse_endpoint(raw: dict) -> GitEndpoint:
    proxy_raw = raw.get("proxy")
    proxy = proxy_raw if isinstance(proxy_raw, str) and proxy_raw.strip() else None

    return GitEndpoint(
        url=raw["url"].strip(),
        proxy=proxy,
        auth=_parse_auth(raw.get("auth", {}))
    )


def _parse_repo(raw: dict) -> RepoConfig:
    return RepoConfig(
        name=raw["name"].strip(),
        dst_override=raw.get("dst_override") or None,
        include_branches=[b for b in raw.get("include_branches", []) if b and b.strip()],
        exclude_branches=[b for b in raw.get("exclude_branches", []) if b and b.strip()],
        sync_tags=bool(raw.get("sync_tags", False))
    )


def parse_config(path: str | Path) -> SyncConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    git_cfg = raw.get("git_config", {})

    sleep_raw = raw.get("wait_next_run_seconds")
    sleep_seconds = 600 if sleep_raw is None else int(sleep_raw)

    return SyncConfig(
        src=_parse_endpoint(git_cfg["src"]),
        dst=_parse_endpoint(git_cfg["dst"]),
        repos=[_parse_repo(r) for r in raw.get("repos", [])],
        temp_dir=raw.get("temp_dir", "/tmp/git-sync"),
        sleep_seconds=sleep_seconds,
        allow_force_push=bool(raw.get("allow_force_push", False))
    )
