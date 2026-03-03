from abc import ABC, abstractmethod
from typing import List
from utils.shell import run_command


class BranchSelector(ABC):
    @abstractmethod
    def select(self, local_path: str) -> List[str]:
        ...


class IncludeListSelector(BranchSelector):
    def __init__(self, branches: List[str]):
        self.branches = branches

    def select(self, local_path: str) -> List[str]:
        return [b.strip() for b in self.branches if b.strip()]


class ExcludeListSelector(BranchSelector):
    def __init__(self, exclude: List[str]):
        self.exclude = set(b.strip() for b in exclude)

    def select(self, local_path: str) -> List[str]:
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
    if include:
        return IncludeListSelector(include)
    return ExcludeListSelector(exclude)
