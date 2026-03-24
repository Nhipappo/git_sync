# git-sync

Утилита для синхронизации Git-репозиториев между двумя Git-серверами через CLI.

## Быстрый старт

### 1. Подготовка конфигурации

Создайте файл `configs/config.yaml` на основе примера:

```bash
cp src/config.yaml.example configs/config.yaml
```

Отредактируйте `configs/config.yaml`, указав ваши серверы и токены.

### 2. Сборка образа

```bash
docker build -f docker/Dockerfile -t git-sync .
```

### 3. Запуск

```bash
docker compose up -d
```

### 4. Просмотр логов

```bash
docker compose logs -f git-sync
```

## Конфигурация

Файл конфигурации: `configs/config.yaml`

```yaml
temp_dir: "/tmp/git-sync" # Директория хранения репозиториев в контейнере
wait_next_run_seconds: 300 # Интервал между запусками синхронизации (секунды)
allow_force_push: false # Включение git push --force

git_config:
  src: # Источник (откуда копировать)
    url: "https://gitlab.example.com"
    auth:
      type: oauth2
      token: <ваш-token> # Токен с правами ReadOnly
    proxy: "http://proxy.example.com:8080" # Опционально: HTTP-прокси
  dst: # Назначение (куда копировать)
    url: "https://gitlab.internal.com"
    auth:
      type: oauth2
      token: <ваш-token> # Токен с правами Read-Write

repos: # Список репозиториев для синхронизации
  - name: group/subgroup/repo # Путь к репозиторию
    exclude_branches: # Исключить эти ветки из синхронизации
      - "dev"
      - "master"
    sync_tags: false # Синхронизировать ли теги
    
  - name: group/another-repo
    include_branches: # Синхронизировать только эти ветки
      - "main"
      - "develop"
    sync_tags: true
    dst_override: destination-group/dest-repo # Опционально: переопределение имени в destination
```

### Параметры репозиториев

| Параметр | Описание |
|----------|----------|
| `name` | Путь к репозиторию на source-сервере (обязательно) |
| `include_branches` | Список веток для синхронизации (если указан — синхронизируются только они) |
| `exclude_branches` | Список веток для исключения (если указан — синхронизируются все, кроме этих) |
| `sync_tags` | Синхронизировать ли теги (по умолчанию `false`) |
| `dst_override` | Переопределение пути репозитория на destination-сервере |

> ⚠️ `include_branches` и `exclude_branches` взаимно исключают друг друга. При указании обоих приоритет у `include_branches`.

## Локальный запуск (без Docker)

```bash
# Установка зависимостей
pip install -r requirements.txt

# Создание конфигурации
cp src/config.yaml.example configs/config.yaml

# Запуск
python src/main.py
```

## Структура проекта

```
.
├── docker/
│   └── Dockerfile       # Docker-образ
├── configs/
│   └── config.yaml      # Конфигурация синхронизации (не версионировать)
├── src/
│   ├── main.py          # Точка входа
│   ├── core/            # Модели и pipeline
│   ├── git/             # Git-клиент и синхронизация
│   ├── rules/           # Селекторы веток
│   └── utils/           # Утилиты (парсер, логгер)
├── docker-compose.yml   # Оркестрация Docker
└── requirements.txt     # Python-зависимости
```

## Зависимости

- Python 3.11+
- Docker и Docker Compose
- Системная утилита `git` (внутри контейнера)
