from typing import List, Optional, Tuple
from utils.shell import run_command
from utils.logger import get_logger

logger = get_logger(__name__)


class GitClient:

    def __init__(self, cwd: Optional[str] = None):
        self.cwd = cwd

    def run(self, cmd: List[str]) -> Tuple[bool, str]:
        return run_command(cmd, cwd=self.cwd) 

    def set_proxy(self, proxy: Optional[str]):
        if proxy:
            run_command(["git", "config", "--global", "http.proxy", proxy])
            logger.info(f"Proxy set: {proxy}")
        else:
            run_command(["git", "config", "--global", "--unset", "http.proxy"])
            logger.info("Proxy unset.")

    @staticmethod
    def set_global_settings():
        run_command(["git", "config", "--global", "http.postBuffer",  "1048576000"])
        run_command(["git", "config", "--global", "https.postBuffer", "1048576000"])
        logger.info("Git global settings set.")
