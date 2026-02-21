from abc import ABC, abstractmethod
from typing import List
from utils.shell import run_command


class BranchSelector(ABC):
    """
    Абстрактный базовый класс для правил выбора веток.

    Чтобы добавить новое правило синхронизации (regex, prefix, env-переменная и т.д.):
        1. Создать класс-наследник здесь
        2. Добавить ветку в make_selector()
        3. Больше ничего менять не нужно
    """

    @abstractmethod
    def select(self, local_path: str) -> List[str]:
        """
        Возвращает список имён веток для синхронизации.

        Параметры:
            local_path — абсолютный путь к локальному клону репозитория
        """
        ...


class IncludeListSelector(BranchSelector):
    """
    Синхронизирует только явно перечисленные ветки из конфига.

    Используется когда в RepoConfig задан непустой include_branches.
    Не обращается к файловой системе — работает только со списком из конфига.
    """

    def __init__(self, branches: List[str]):
        """
        Параметры:
            branches — список имён веток из поля include_branches конфига
        """
        self.branches = branches

    def select(self, local_path: str) -> List[str]:
        """
        Возвращает очищенный список веток из конфига.
        local_path не используется — ветки известны заранее.
        """
        return [b.strip() for b in self.branches if b.strip()]


class ExcludeListSelector(BranchSelector):
    """
    Синхронизирует все локальные ветки кроме перечисленных в exclude_branches.

    Используется по умолчанию когда include_branches не задан.
    Читает актуальный список веток из локального репозитория через git branch.
    """

    def __init__(self, exclude: List[str]):
        """
        Параметры:
            exclude — список имён веток, которые НЕ нужно синхронизировать
        """
        self.exclude = set(b.strip() for b in exclude)

    def select(self, local_path: str) -> List[str]:
        """
        Получает список локальных веток и исключает из него exclude-список.
        """
        ok, out = run_command(["git", "branch", "--list"], cwd=local_path)
        if not ok:
            return []
        branches = [
            b.strip().lstrip("*").strip()
            for b in out.splitlines()
            if b.strip()
        ]
        return [b for b in branches if b and b not in self.exclude]


def make_selector(include: List[str], exclude: List[str]) -> BranchSelector:
    """
    Фабрика: выбирает нужный селектор на основе конфига репозитория.

    Логика:
        include задан → IncludeListSelector (точный список)
        include пуст  → ExcludeListSelector (все минус exclude)
    """
    if include:
        return IncludeListSelector(include)
    return ExcludeListSelector(exclude)
