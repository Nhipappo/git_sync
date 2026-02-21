import subprocess
from typing import List, Optional, Tuple


def run_command(cmd: List[str], cwd: Optional[str] = None) -> Tuple[bool, str]:
    """
    Универсальный запуск любой shell-команды.

    Параметры:
        cmd  — список аргументов, например ["git", "clone", url, path]
        cwd  — рабочая директория; None = текущая директория процесса

    Возвращает:
        (True,  stdout+stderr) — если returncode == 0
        (False, stdout+stderr) — если returncode != 0
        (False, str(exception)) — если произошло исключение ОС
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False          
        )                        
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)
