import os
import time
from core.models import SyncConfig
from git.client import GitClient
from git.sync import update_repo, push_repo
from utils.logger import get_logger

logger = get_logger(__name__)


def run_pipeline(config: SyncConfig):
    GitClient.set_global_settings()
    os.makedirs(config.temp_dir, exist_ok=True)

    git_client = GitClient()
    run = 0

    while True:
        run += 1
        logger.info(f"\033[1;33mRun: [{run}]\033[0m")
        total = len(config.repos)

        for i, repo in enumerate(config.repos, 1):
            bar = "#" * i + " " * (total - i)
            logger.info(f"\033[1;35mProgress: [{bar}] ({i}/{total}) Repo: '{repo.name}'\033[0m")

            try:
                git_client.set_proxy(config.src.proxy)
                update_repo(repo, config.src.authed_url, config.temp_dir)

                git_client.set_proxy(config.dst.proxy)
                push_repo(repo, config.dst.authed_url, config.temp_dir, config)

            except Exception as e:
                logger.error(f"Unhandled error for repo '{repo.name}': {e}")

        logger.info(f"Sleeping {config.sleep_seconds}s until next run.")
        time.sleep(config.sleep_seconds)
