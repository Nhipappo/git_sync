from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AuthConfig:
    """
    Конфигурация авторизации для одного Git-эндпоинта.

    Поля:
        type  — тип авторизации: "oauth2" или "none"
        token — токен (только для type="oauth2")
    """
    type: str
    token: Optional[str] = None

    def inject_into_url(self, url: str) -> str:
        """
        Встраивает токен прямо в URL в формате oauth2.

        Пример:
            "https://gitlab.com/org" + token "abc123"
            → "https://oauth2:abc123@gitlab.com/org"
        """
        if self.type == "oauth2" and self.token:
            if "://" in url:
                scheme, rest = url.split("://", 1)
            else:
                scheme, rest = "https", url
            return f"{scheme}://oauth2:{self.token}@{rest}"
        return url


@dataclass
class GitEndpoint:
    """
    Описывает один Git-сервер (источник или назначение).

    Поля:
        url   — базовый URL сервера без имени репозитория
        proxy — HTTP-прокси или None если прямое подключение
        auth  — объект авторизации
    """
    url: str
    proxy: Optional[str]
    auth: AuthConfig

    @property
    def authed_url(self) -> str:
        """
        Возвращает URL с уже встроенным токеном авторизации.
        """
        return self.auth.inject_into_url(self.url)


@dataclass
class RepoConfig:
    """
    Конфигурация одного репозитория для синхронизации.

    Поля:
        name             — "group/repo" или просто "repo"
        dst_override     — имя репозитория на dst, если оно отличается от src
        include_branches — если задан, синхронизировать только эти ветки
        exclude_branches — если include пуст, исключить эти ветки из всех
        sync_tags        — пушить ли теги в dst
    """
    name: str
    dst_override: Optional[str] = None
    include_branches: List[str] = field(default_factory=list)
    exclude_branches: List[str] = field(default_factory=list)
    sync_tags: bool = False

    @property
    def path(self) -> str:
        """
        Возвращает группу/namespace репозитория.

        Примеры:
            "group/repo"       → "group"
            "org/team/repo"    → "org/team"
            "repo"             → "" 
        """
        return self.name.rsplit("/", 1)[0] if "/" in self.name else ""

    @property
    def repo_name(self) -> str:
        """
        Возвращает только имя репозитория без группы.

        Примеры:
            "group/repo"  → "repo"
            "repo"        → "repo"
        """
        return self.name.rsplit("/", 1)[-1]


@dataclass
class SyncConfig:
    """
    Корневой объект конфигурации всего процесса синхронизации.
    Создаётся парсером (utils/parser.py) и передаётся в pipeline.

    Поля:
        src              — источник (откуда клонировать)
        dst              — назначение (куда пушить)
        repos            — список репозиториев
        temp_dir         — локальная папка для хранения клонов
        sleep_seconds    — пауза между циклами синхронизации
        allow_force_push — разрешить --force при push во все репозитории
    """
    src: GitEndpoint
    dst: GitEndpoint
    repos: List[RepoConfig]
    temp_dir: str = "/tmp/git-sync"
    sleep_seconds: int = 600
    allow_force_push: bool = False
