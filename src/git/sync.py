import os
import shutil
from typing import List
from core.models import RepoConfig, SyncConfig
from git.client import GitClient
from rules.branch_selector import make_selector
from utils.logger import get_logger

logger = get_logger(__name__)


def _parse_date_to_timestamp(date_str: str) -> int:
    from datetime import datetime
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return 0


def should_push(src_commit: dict | None, dst_commit: dict | None, branch: str) -> str:
    if not src_commit:
        return "dst_to_src"
    if not dst_commit:
        return "src_to_dst"
    if src_commit["hash"] == dst_commit["hash"]:
        return "skip"

    src_ts = _parse_date_to_timestamp(src_commit["date"])
    dst_ts = _parse_date_to_timestamp(dst_commit["date"])

    if src_ts > dst_ts:
        if '[sync]' in src_commit["message"].lower():
            return "skip"
        return "src_to_dst"
    elif src_ts < dst_ts:
        return "dst_to_src"
    else:
        return "skip"   


def _format_commit_info(commit: dict | None) -> str:
    if not commit:
        return "none"
    timestamp = _parse_date_to_timestamp(commit["date"])
    msg = commit["message"][-50:].replace('\n', ' ')
    return f"{timestamp} '{msg}'"


def add_sync_marker(client: GitClient, branch: str) -> bool:
    ok, out = client.run(["git", "log", "-1", "--format=%B", branch])
    if not ok or not out.strip():
        logger.error(f"Failed to get commit message for {branch}")
        return False

    current_message = out.strip()

    if '[sync]' in current_message.lower():
        logger.info(f"Commit already has [sync] marker: {branch}")
        return True

    new_message = f"{current_message} [sync]"

    logger.info(f"Adding [sync] marker commit on {branch}")

    ok, log = client.run(["git", "commit", "--allow-empty", "-m", new_message])
    if not ok:
        logger.error(f"Failed to add sync marker commit on {branch}: {log}")
        return False

    logger.info(f"Successfully added [sync] marker commit to {branch}")
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
    logger.info(f"Cloning: {repo.name} from {remote}")
    success, log = client.run(["git", "clone", remote, local])
    _log_result(success, log, "Repository cloned.", "Clone failed.")
    return success


def update_repo(repo: RepoConfig, src_url: str, temp_dir: str) -> bool:
    local = _local_path(temp_dir, repo)

    if not os.path.isdir(local):
        logger.info(f"Clone: {repo.name} from {src_url}")
        return clone_repo(repo, src_url, temp_dir)

    logger.info(f"Update: {repo.name}")
    
    client = GitClient(cwd=local)

    _track_remote_branches(client)     
    _delete_gone_branches(client)
    _pull_all_branches(client)

    for cmd in [
        ["git", "fetch", "--all", "--prune"],
        ["git", "pull", "--all"],
        ["git", "fetch", "--tags", "--prune-tags"],
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

    if src_url:
        src_remote_url = f"{src_url}/{repo.name}.git"
        client.run(["git", "remote", "add", "src", src_remote_url])

    logger.info(f"Sync: {repo.name} (src) <-> {dst_name} (dst)")

    selector = make_selector(repo.include_branches, repo.exclude_branches)
    branches = selector.select(local)

    FATAL_ERRORS = (
            "repository not found",
            "does not exist",
            "remote: repository not found",
            "fatal: repository",

        )

    for i, branch in enumerate(branches, 1):
        src_commit = client.get_commit_info(branch)

        client.run(["git", "fetch", "ext", branch])
        dst_commit = client.get_commit_info(f"ext/{branch}")

        direction = should_push(src_commit, dst_commit, branch)

        if direction == "skip":
            src_info = _format_commit_info(src_commit)
            dst_info = _format_commit_info(dst_commit)
            logger.info(f"Branch '{branch}': skip ({repo.name}={src_info}, {dst_name}={dst_info})")
            continue

        if direction == "dst_to_src":
            src_info = _format_commit_info(src_commit)
            dst_info = _format_commit_info(dst_commit)
            logger.info(f"Branch '{branch}': dst_to_src ({repo.name}={src_info}, {dst_name}={dst_info})")

            client.run(["git", "fetch", "ext", branch])

            ok, current_branch = client.run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            current_branch = current_branch.strip() if ok else "main"

            temp_branch = f"tmp_sync_{branch.replace('/', '_')}"
            client.run(["git", "checkout", "-f", "-B", temp_branch, f"ext/{branch}"])

            sync_added = add_sync_marker(client, temp_branch)
            logger.info(f"add_sync_marker result: {sync_added} for {temp_branch}")

            cmd = ["git", "push", "--force", "src", f"{temp_branch}:{branch}"]
            success, log = client.run(cmd)
            _log_result(success, log, f"Branch '{branch}' pushed to src.", f"Push to src error: {repo.name}")

            client.run(["git", "checkout", current_branch])
            client.run(["git", "branch", "-D", temp_branch])

            is_fatal = any(e in log.lower() for e in FATAL_ERRORS)
            if not success and is_fatal:
                break
            continue

        src_info = _format_commit_info(src_commit)
        dst_info = _format_commit_info(dst_commit)
        logger.info(f"Pushing branch: {branch} [{i}/{len(branches)}] ({repo.name}={src_info} -> {dst_name}={dst_info})")

        client.run(["git", "checkout", "-f", branch])

        sync_added = add_sync_marker(client, branch)
        logger.info(f"add_sync_marker result: {sync_added} for {branch}")

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
            parts = line.split()
            if parts[0] == "*":
                continue
            branch = parts[0].strip()
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
