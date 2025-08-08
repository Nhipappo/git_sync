# git-sync

Скрипт синхронизации git-серверов через cli git

## Быстрый старт

Собрать образ: `docker build -f .\docker\Dockerfile -t git-sync .`

Запустить docker-compose: `docker compose up -d`

## Конфигурация

```yaml
temp_dir: "/tmp/git-sync" # Директория хранения репозиториев в локальной файловой системе
wait_next_run_seconds: 300 # Ожидание до следующего запуска синхронизации всех репозиториев
allow_force_push: false # Включение/отключение git push --force

git_config: # Конфигурация git'ов
  src: # Источник (откуда копировать)
    url: "https://gitlab.extserv.ru" # url-адрес гита
    auth:
      type: oauth2 # Тип авторизации. Возможные варианты: oauth2
      token: xZxZxZxZxZxZx # Токен доступа к гиту. ReadOnly
    proxy: "http://spb99-prx-a.gazprom-neft.local:8090" # Использование прокси. Если указано, будет установлено прокси, иначе - unset
  dst: # Назначение (куда копировать)
    url: "http://oms02-cvtrdev.gazprom-neft.local:9099"
    auth:
      type: oauth2
      token: xZxZxZxZxZxZx # Токен доступа к гиту. Read-Write

repos: # Список репозиториев
  - name: dsutp/core # Имя = путь до репозитория subgroups/name
    exclude_branches: # Список веток, которые исключить из синхронизации
      - "dev"
      - "master"
      - "main"
    sync_tags: false # Синхронизировать ли теги
  - name: dsutp/ec/frontend
    include_branches: # Список веток, которые включить в синхронизацию
      - "dev"
      - "master"
      - "main"
    sync_tags: false
```

`include_branches` и `exclude_branches` - Синхронизировать только '_include_branches_', иначе синхронизировать все, исключив '_exclude_branches_'
