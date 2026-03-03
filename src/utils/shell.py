import subprocess
from typing import List, Optional, Tuple


def run_command(cmd: List[str], cwd: Optional[str] = None) -> Tuple[bool, str]:
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
