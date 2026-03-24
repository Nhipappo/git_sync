import os
import shutil
from typing import List
from core.models import RepoConfig, SyncConfig
from git.client import GitClient
from rules.branch_selector import make_selector
from utils.logger import get_logger

logger = get_logger(__name__)


def should_push(src_commit: dict | None, dst_commit: dict | None, branch: str) -> str:
    """
    Определяет направление синхронизации для ветки.
    
    ЗАМЕНИ ЭТУ ФУНКЦИЮ НА СВОЮ ЛОГИКУ.
    
    Args:
        src_commit: {"hash": ..., "date": ..., "author": ..., "message": ...} или None
        dst_commit: {"hash": ..., "date": ..., "author": ..., "message": ...} или None
        branch: Имя ветки
    
    Returns:
        "src_to_dst" | "dst_to_src" | "skip"
    """
    if not src_commit:
        return "skip"
    if not dst_commit:
        return "src_to_dst"
    if src_commit["hash"] == dst_commit["hash"]:
        return "skip"
    
    # Если уже есть [sync] — не синхронизируем (защита от зацикливания)
    if '[sync]' in src_commit["message"].lower():
        return "skip"
    if '[sync]' in dst_commit["message"].lower():
        return "skip"
    
    # Определяем направление по дате
    if src_commit["date"] > dst_commit["date"]:
        return "src_to_dst"
    else:
        return "dst_to_src"


def add_sync_marker(client: GitClient, branch: str) -> bool:
    """
    Добавляет [sync] к сообщению последнего коммита.
    
    Args:
        client: GitClient с установленным cwd в репозиторий
        branch: Имя ветки
    
    Returns:
        True если успешно, False если ошибка
    """
    # Получаем текущее сообщение коммита
    ok, out = client.run(["git", "log", "-1", "--format=%B", branch])
    if not ok or not out.strip():
        return False
    
    current_message = out.strip()
    
    # Добавляем [sync] если ещё нет
    if '[sync]' in current_message.lower():
        return True  # Уже есть маркер
    
    new_message = f"{current_message}\n\n[sync]"
    
    # Делаем amend с новым сообщением
    ok, log = client.run(["git", "commit", "--amend", "-m", new_message])
    return ok


def _local_path(temp_dir: str, repo: RepoConfig) -> str:
    return os.path.join(temp_dir, repo.name)


def clone_repo(repo: RepoConfig, src_url: str, temp_dir: str) -> bool:
    local = _local_path(temp_dir, repo)

    if os.path.exists(local):
        shutil.rmtree(local)

    os.makedirs(os.path.dirname(local) or temp_dir, exist_ok=True)

    client = GitClient()
    remote = f"{src_url}/{repo.name}.git"
    success, log = client.run(["git", "clone", remote, local])
    _log_result(success, log, "Repository cloned.", "Clone failed.")
    return success


def update_repo(repo: RepoConfig, src_url: str, temp_dir: str) -> bool:
    local = _local_path(temp_dir, repo)

    if not os.path.isdir(local):
        return clone_repo(repo, src_url, temp_dir)

    client = GitClient(cwd=local)

    _track_remote_branches(client)     
    _delete_gone_branches(client)
    _pull_all_branches(client)

    for cmd in [
        ["git", "fetch", "--all", "--prune"],
        ["git", "pull", "--all"],
        ["git", "fetch", "--tags", "--prune-tags"],
        ["git", "pull", "--tags"],
    ]:
        success, log = client.run(cmd)
        if not success:
            _log_result(False, log, "", "Update error — recloning.")
            return clone_repo(repo, src_url, temp_dir)
        _log_result(True, log, "Updated.", "")

    return True


def push_repo(repo: RepoConfig, dst_url: str, temp_dir: str, config: SyncConfig, src_url: str = None) -> bool:
    local = _local_path(temp_dir, repo)
    client = GitClient(cwd=local)

    dst_name = repo.dst_override or repo.name
    dst_remote_url = f"{dst_url}/{dst_name}.git"
    client.run(["git", "remote", "add", "ext", dst_remote_url])
    
    # Добавляем remote для источника (нужен для dst_to_src)
    if src_url:
        src_remote_url = f"{src_url}/{repo.name}.git"
        client.run(["git", "remote", "add", "src", src_remote_url])

    selector = make_selector(repo.include_branches, repo.exclude_branches)
    branches = selector.select(local)

    FATAL_ERRORS = (
            "repository not found",
            "does not exist",
            "remote: repository not found",
            "fatal: repository",

        )

    for i, branch in enumerate(branches, 1):
        # Получаем информацию о коммитах
        src_commit = client.get_commit_info(branch)

        # Fetch remote ветку и получаем коммит dst
        client.run(["git", "fetch", "ext", branch])
        dst_commit = client.get_commit_info(f"ext/{branch}")

        # Определяем направление синхронизации
        direction = should_push(src_commit, dst_commit, branch)

        if direction == "skip":
            src_hash = src_commit["hash"][:7] if src_commit else "none"
            dst_hash = dst_commit["hash"][:7] if dst_commit else "none"
            logger.info(f"Branch '{branch}': skip (src={src_hash}, dst={dst_hash})")
            continue

        if direction == "dst_to_src":
            # Пуш из dst в src (reverse sync)
            src_hash = src_commit["hash"][:7] if src_commit else "none"
            dst_hash = dst_commit["hash"][:7] if dst_commit else "none"
            logger.info(f"Branch '{branch}': dst_to_src (src={src_hash}, dst={dst_hash})")

            # Fetch ext remote (dst) чтобы получить актуальный коммит
            client.run(["git", "fetch", "ext", branch])
            
            # Сохраняем текущую ветку
            ok, current_branch = client.run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            current_branch = current_branch.strip() if ok else "main"
            
            # Создаём временную ветку для работы (чтобы не ломать текущую)
            temp_branch = f"tmp_sync_{branch.replace('/', '_')}"
            client.run(["git", "checkout", "-B", temp_branch, f"ext/{branch}"])
            
            # Добавляем [sync] к коммиту
            add_sync_marker(client, temp_branch)

            # Пушим dst-коммит в src
            cmd = ["git", "push", "--force", "src", f"{temp_branch}:{branch}"]
            success, log = client.run(cmd)
            _log_result(success, log, f"Branch '{branch}' pushed to src.", f"Push to src error: {repo.name}")

            # Возвращаемся на исходную ветку, удаляем временную
            client.run(["git", "checkout", current_branch])
            client.run(["git", "branch", "-D", temp_branch])

            is_fatal = any(e in log.lower() for e in FATAL_ERRORS)
            if not success and is_fatal:
                break
            continue

        # direction == "src_to_dst"
        src_hash = src_commit["hash"][:7] if src_commit else "none"
        dst_hash = dst_commit["hash"][:7] if dst_commit else "none"
        logger.info(f"Pushing branch: {branch} [{i}/{len(branches)}] (src={src_hash}, dst={dst_hash})")
        
        # Добавляем [sync] к коммиту
        add_sync_marker(client, branch)
        
        cmd = ["git", "push", "ext", branch]
        if config.allow_force_push:
            cmd.insert(3, "--force")
        success, log = client.run(cmd)
        _log_result(success, log, f"Branch '{branch}' pushed.", f"Push error: {repo.name}")

        is_fatal = any(e in log.lower() for e in FATAL_ERRORS)
        if not success and is_fatal:
            break

    if repo.sync_tags:
        success, log = client.run(["git", "push", "ext", "--force", "--tags"])
        _log_result(success, log, "Tags pushed.", f"Tags push error: {repo.name}")
    else:
        logger.info("Tags sync skipped (sync_tags=false).")

    client.run(["git", "remote", "remove", "ext"])
    if src_url:
        client.run(["git", "remote", "remove", "src"])
    return True


def _log_result(success: bool, log: str, ok_msg: str, err_msg: str):
    log_fn = logger.info if success else logger.error
    message = ok_msg if success else err_msg
    if message:
        log_fn(message)
    for line in log.splitlines():
        if line.strip():
            log_fn(line.strip())


def _track_remote_branches(client: GitClient):
    ok, out = client.run(["git", "branch", "-r"])
    if not ok:
        return
    for remote in out.splitlines():
        remote = remote.strip()
        if "->" not in remote and remote:
            branch = remote.replace("origin/", "").strip()
            if branch and branch != "HEAD":
                client.run(["git", "branch", "--track", branch, remote])


def _delete_gone_branches(client: GitClient):
    ok, out = client.run(["git", "branch", "-vv"])
    if not ok:
        return
    for line in out.splitlines():
        if ": gone]" in line:
            branch = line.split()[0].strip()
            if branch:
                client.run(["git", "branch", "-D", branch])


def _pull_all_branches(client: GitClient):
    ok, out = client.run(["git", "branch", "-r"])
    if not ok:
        return
    for remote in out.splitlines():
        remote = remote.strip()
        if "->" not in remote and remote:
            branch = remote.replace("origin/", "").strip()
            if branch and branch != "HEAD":
                client.run(["git", "checkout", branch])
                client.run(["git", "pull"])
