import os
import shutil
from typing import List
from core.models import RepoConfig, SyncConfig
from git.client import GitClient
from rules.branch_selector import make_selector
from utils.logger import get_logger

logger = get_logger(__name__)


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


def push_repo(repo: RepoConfig, dst_url: str, temp_dir: str, config: SyncConfig) -> bool:
    local = _local_path(temp_dir, repo)
    client = GitClient(cwd=local)

    dst_name = repo.dst_override or repo.name
    remote_url = f"{dst_url}/{dst_name}.git"
    client.run(["git", "remote", "add", "ext", remote_url])

    selector = make_selector(repo.include_branches, repo.exclude_branches)
    branches = selector.select(local)

    FATAL_ERRORS = (
            "repository not found",
            "does not exist",
            "remote: repository not found",
            "fatal: repository",
            
        )

    for i, branch in enumerate(branches, 1):
        logger.info(f"Pushing branch: {branch} [{i}/{len(branches)}]")
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
