import os
import sys
import subprocess
import time
import logging
import yaml
from pathlib import Path
from typing import Optional, List, Tuple

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='|\033[1;35m|\033[1;36m [INFO]\033[0m %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def run_command(cmd: List[str], cwd: Optional[str] = None) -> Tuple[bool, str]:
    """Запускает команду и возвращает (успех, вывод)"""
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


def set_git_global_settings():
    """Настраивает глобальные параметры git"""
    logger.info("Git global settings set.")
    run_command(["git", "config", "--global", "http.postBuffer", "1048576000"])
    run_command(["git", "config", "--global", "https.postBuffer", "1048576000"])


def make_oauth2_url(url: str, token: str) -> str:
    """Встраивает oauth2 токен в URL"""
    url = url.strip()
    token = token.strip()
    
    if "://" in url:
        scheme, no_scheme = url.split("://", 1)
    else:
        scheme, no_scheme = "https", url
    
    return f"{scheme}://oauth2:{token}@{no_scheme}"


def setup_git_env(git_config: dict, config_path: str) -> Tuple[str, Optional[str]]:
    """Настраивает URL и прокси для src/dst"""
    url = yaml.safe_load(subprocess.run(
        ["yq", f".{git_config['path']}.url", config_path],
        capture_output=True, text=True, check=True
    ).stdout.strip())
    
    proxy = yaml.safe_load(subprocess.run(
        ["yq", f".{git_config['path']}.proxy", config_path],
        capture_output=True, text=True, check=True
    ).stdout.strip())
    
    auth_type = yaml.safe_load(subprocess.run(
        ["yq", f".{git_config['path']}.auth.type", config_path],
        capture_output=True, text=True, check=True
    ).stdout.strip())
    
    if auth_type == "oauth2":
        token = yaml.safe_load(subprocess.run(
            ["yq", f".{git_config['path']}.auth.token", config_path],
            capture_output=True, text=True, check=True
        ).stdout.strip())
        url = make_oauth2_url(url, token)
    
    return url, proxy if proxy != "null" else None


def set_proxy(proxy: Optional[str]):
    """Устанавливает или удаляет прокси"""
    if proxy is None or proxy == "null":
        run_command(["git", "config", "--global", "--unset", "http.proxy"])
        logger.info("Proxy unset.")
    else:
        run_command(["git", "config", "--global", "http.proxy", proxy])
        logger.info(f"Proxy set: {proxy}.")


def clone_repo(git_url: str, path: str, name: str, temp_dir: str) -> bool:
    """Клонирует репозиторий с пересозданием"""
    logger.info("Git clone.")
    
    repo_path = f"{path}/{name}" if path else name
    local_path = os.path.join(temp_dir, repo_path)
    
    # Удаляем старую копию
    if os.path.exists(local_path):
        import shutil
        shutil.rmtree(local_path)
    
    # Создаём директорию
    os.makedirs(os.path.dirname(local_path) if path else temp_dir, exist_ok=True)
    
    success, log = run_command([
        "git", "clone", f"{git_url}/{path}/{name}.git" if path else f"{git_url}/{name}.git",
        local_path
    ])
    
    if success:
        logger.info("Local repository successfully cloned:")
        for line in log.splitlines():
            logger.info(line.strip())
    else:
        logger.error(f"Error cloning git:")
        for line in log.splitlines():
            logger.error(line.strip())
    
    return success


def update_repo(path: str, name: str, temp_dir: str, src_git_url: str) -> bool:
    """Обновляет локальный репозиторий"""
    logger.info("Git update.")
    
    repo_path = f"{path}/{name}" if path else name
    local_path = os.path.join(temp_dir, repo_path)
    
    if not os.path.isdir(local_path):
        return clone_repo(src_git_url, path, name, temp_dir)
    
    commands = [
        ["git", "fetch", "--all", "--prune"],
        ["git", "pull", "--all"],
        ["git", "fetch", "--tags", "--prune-tags"],
        ["git", "pull", "--tags"],
    ]
    
    # Трекаем удалённые ветки
    success, branches = run_command(["git", "branch", "-r"], cwd=local_path)
    if success:
        for remote in branches.splitlines():
            remote = remote.strip()
            if "->" not in remote and remote:
                branch_name = remote.replace("origin/", "").strip()
                if branch_name and branch_name != "HEAD":
                    run_command(["git", "branch", "--track", branch_name, remote], cwd=local_path)
    
    # Удаляем удалённые ветки
    success, gone = run_command(
        ["git", "branch", "-vv"], cwd=local_path
    )
    if success:
        for line in gone.splitlines():
            if ": gone]" in line:
                branch = line.split()[0].strip()
                if branch:
                    run_command(["git", "branch", "-D", branch], cwd=local_path)
    
    # Пуллим все ветки
    success, remote_branches = run_command(["git", "branch", "-r"], cwd=local_path)
    if success:
        for remote in remote_branches.splitlines():
            remote = remote.strip()
            if "->" not in remote and remote:
                branch = remote.replace("origin/", "").strip()
                if branch and branch != "HEAD":
                    run_command(["git", "checkout", branch], cwd=local_path)
                    run_command(["git", "pull"], cwd=local_path)
    
    # Выполняем основные команды
    all_success = True
    for cmd in commands:
        success, log = run_command(cmd, cwd=local_path)
        if not success:
            all_success = False
            logger.warning(f"Local repository update error:")
            for line in log.splitlines():
                logger.warning(line.strip())
            # Пробуем переклонировать при ошибке
            return clone_repo(src_git_url, path, name, temp_dir)
        else:
            logger.info(f"Local repository successfully updated:")
            for line in log.splitlines():
                logger.info(line.strip())
    
    return all_success


def selecting_branches(path: str, name: str, temp_dir: str, 
                       config: dict, repo_name: str) -> List[str]:
    """Выбирает ветки для синхронизации (чистый Python, без yq)"""
    logger.info("Selecting branches.")
    
    repo_path = f"{path}/{name}" if path else name
    local_path = os.path.join(temp_dir, repo_path)
    
    # Находим нужный репозиторий в конфиге
    repo_config = None
    for repo in config.get('repos', []):
        if repo.get('name') == repo_name:
            repo_config = repo
            break
    
    if not repo_config:
        logger.warning(f"Repo '{repo_name}' not found in config")
        return []
    
    include_branches = repo_config.get('include_branches', [])
    exclude_branches = repo_config.get('exclude_branches', [])
    
    if include_branches:
        # Если include задан — используем только его
        return [b.strip() for b in include_branches if b.strip()]
    else:
        # Иначе берём все локальные ветки, кроме exclude
        success, all_branches = run_command(["git", "branch", "--list"], cwd=local_path)
        if not success:
            return []
        
        all_branches = [
            b.strip().replace("* ", "") 
            for b in all_branches.splitlines() 
            if b.strip()
        ]
        
        exclude_set = set(b.strip() for b in exclude_branches if b.strip())
        return [b for b in all_branches if b not in exclude_set]


def push_repo(git_url: str, path: str, name: str, temp_dir: str, 
              config_path: str, repo_name: str, selected_branches: List[str]) -> bool:
    """Пушит локальный репозиторий в dst"""
    repo_path = f"{path}/{name}" if path else name
    local_path = os.path.join(temp_dir, repo_path)
    
    logger.info(f"Git push: '{local_path}'.")
    
    # Читаем dst_override из конфига
    import subprocess
    result = subprocess.run(
        ["yq", f".repos.[] | select(.name == \"{repo_name}\") | .dst_override // \"{name}\"", config_path],
        capture_output=True, text=True
    )
    dst_repo_name = result.stdout.strip()
    if not dst_repo_name or dst_repo_name == "null":
        dst_repo_name = name
    
    # Собираем dst путь
    if "/" in dst_repo_name:
        dst_path, dst_name = dst_repo_name.rsplit("/", 1)
        dst_remote_url = f"{git_url}/{dst_path}/{dst_name}.git"
    else:
        dst_remote_url = f"{git_url}/{dst_repo_name}.git"
    
    # Добавляем remote
    run_command(["git", "remote", "add", "ext", dst_remote_url], cwd=local_path)
    
    # Пушим ветки
    allow_force = subprocess.run(
        ["yq", ".allow_force_push", config_path],
        capture_output=True, text=True
    ).stdout.strip() == "true"
    
    for i, branch in enumerate(selected_branches, 1):
        logger.info(f"Pushing a branch: {branch} [{i}/{len(selected_branches)}]")
        
        cmd = ["git", "push", "ext", "--force", branch] if allow_force else ["git", "push", "ext", branch]
        success, log = run_command(cmd, cwd=local_path)
        
        if success:
            logger.info(f"Branch '{branch}' successfully pushed:")
            for line in log.splitlines():
                logger.info(line.strip())
        elif "128" in log or "not found" in log.lower():
            logger.error(f"Please, create repository or add access: {path}/{name}. Error:")
            for line in log.splitlines():
                logger.error(line.strip())
            break
        else:
            logger.error(f"Error pushing to remote repository: {path}/{name}. Error:")
            for line in log.splitlines():
                logger.error(line.strip())
    
    # Пушим теги
    sync_tags = subprocess.run(
        ["yq", f".repos.[] | select(.name == \"{repo_name}\") | .sync_tags", config_path],
        capture_output=True, text=True
    ).stdout.strip()
    
    if sync_tags == "true":
        logger.info("Pushing all tags.")
        success, log = run_command(["git", "push", "ext", "--force", "--tags"], cwd=local_path)
        if success:
            logger.info("All tags successfully pushed:")
            for line in log.splitlines():
                logger.info(line.strip())
        else:
            logger.error(f"Please, create repository or add access: {path}/{name}. Error:")
            for line in log.splitlines():
                logger.error(line.strip())
    else:
        logger.info(f"Pushing tags is skipped because sync_tags: '{sync_tags}'.")
    
    # Удаляем remote
    run_command(["git", "remote", "remove", "ext"], cwd=local_path)
    return True


def parse_repo_path(repo: str) -> Tuple[str, str]:
    """Разбирает 'group/repo' или 'repo' на (path, name)"""
    if "/" in repo:
        return repo.rsplit("/", 1)
    return "", repo


def main():
    """Основная функция"""
    # Пути к конфигу
    script_dir = Path(__file__).parent.resolve()
    config_path = str(script_dir / "../config.yaml")
    
    # Читаем базовые параметры
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    temp_dir = config.get("temp_dir", "/tmp/git-sync")
    repos = [r["name"] for r in config.get("repos", [])]
    sleep_seconds = config.get("wait_next_run_seconds", 600)
    if sleep_seconds is None:
        sleep_seconds = 600
    
    # Настраиваем git
    set_git_global_settings()
    
    # Создаём temp_dir
    os.makedirs(temp_dir, exist_ok=True)
    
    # Настраиваем src/dst окружение
    src_git_url, src_proxy = setup_git_env({"path": "git_config.src"}, config_path)
    dst_git_url, dst_proxy = setup_git_env({"path": "git_config.dst"}, config_path)
    
    runs_iter = 0
    
    while True:
        runs_iter += 1
        logger.info(f"\033[1;33mLounch: [{runs_iter}]\033[0m")
        
        for repo_iter, repo in enumerate(repos, 1):
            # Прогресс-бар
            bar = "#" * repo_iter + " " * (len(repos) - repo_iter)
            repo = repo.strip()
            logger.info(f"\033[1;35mProgress: [{bar}]\033[0m")
            logger.info(f"\033[1;35mRepo: '{repo}'.\033[0m")
            
            # Парсим путь/имя
            repo_path, repo_name = parse_repo_path(repo)
            
            # Прокси для src
            set_proxy(src_proxy)
            
            # Клонируем или пропускаем
            local_repo_path = os.path.join(temp_dir, repo_path, repo_name) if repo_path else os.path.join(temp_dir, repo_name)
            if os.path.isdir(local_repo_path):
                logger.info("Repository already exist. Skip clone.")
            else:
                clone_repo(src_git_url, repo_path, repo_name, temp_dir)
            
            # Обновляем
            update_repo(repo_path, repo_name, temp_dir, src_git_url)
            
            # Выбираем ветки
            selected_branches = selecting_branches(repo_path, repo_name, temp_dir, config, repo)
            
            # Прокси для dst
            set_proxy(dst_proxy)
            
            # Пушим
            push_repo(dst_git_url, repo_path, repo_name, temp_dir, config_path, repo, selected_branches)
        
        logger.info(f"Waiting for the next run: {sleep_seconds} seconds.")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()