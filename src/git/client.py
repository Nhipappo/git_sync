from typing import List, Optional, Tuple
from utils.shell import run_command
from utils.logger import get_logger

logger = get_logger(__name__)


class GitClient:
    """
    Низкоуровневая обёртка над git CLI.

    Каждый экземпляр привязан к конкретной рабочей директории (cwd).
    Это устраняет необходимость передавать путь в каждый вызов вручную.

    Использование:
        client = GitClient(cwd="/tmp/git-sync/myrepo")
        ok, out = client.run(["git", "status"])
    """

    def __init__(self, cwd: Optional[str] = None):
        """
        Параметры:
            cwd — рабочая директория для всех команд этого клиента.
                  None означает текущую директорию процесса.
        """
        self.cwd = cwd

    def run(self, cmd: List[str]) -> Tuple[bool, str]:
        """
        Выполняет git-команду в self.cwd.

        Параметры:
            cmd — список аргументов, например ["git", "fetch", "--all"]

        Возвращает:
            (True, output)  — команда завершилась успешно
            (False, output) — команда завершилась с ошибкой

        """
        return run_command(cmd, cwd=self.cwd) 

    def set_proxy(self, proxy: Optional[str]):
        """
        Устанавливает или снимает HTTP-прокси глобально для git.

        Вызывается перед каждой операцией с src или dst,
        потому что у них могут быть разные прокси-настройки.

        """
        if proxy:
            run_command(["git", "config", "--global", "http.proxy", proxy])
            logger.info(f"Proxy set: {proxy}")
        else:
            run_command(["git", "config", "--global", "--unset", "http.proxy"])
            logger.info("Proxy unset.")

    @staticmethod
    def set_global_settings():
        """
        Устанавливает глобальные параметры git один раз при старте.

        postBuffer=1048576000 (~1 ГБ)
        """
        run_command(["git", "config", "--global", "http.postBuffer",  "1048576000"])
        run_command(["git", "config", "--global", "https.postBuffer", "1048576000"])
        logger.info("Git global settings set.")
