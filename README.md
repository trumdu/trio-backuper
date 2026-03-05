# trio-backuper

Централизованный бэкапер для **PostgreSQL**, **MongoDB** и **S3‑совместимого хранилища** (MinIO).

## Быстрый старт (Docker)

1) Скопируйте пример окружения:

- Windows (PowerShell):

```powershell
Copy-Item .env.example .env
```

2) Сгенерируйте ключ шифрования и вставьте в `.env` значение `SECRETS_FERNET_KEY`:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

3) Запустите:

```powershell
docker compose up --build
```

Откройте веб‑интерфейс: `http://localhost:8000`

## Данные и тома

По умолчанию `docker-compose.yml` монтирует `./data` в контейнер как `/data`:

- SQLite: `/data/app.db`
- логи приложения: `/data/logs/app.log`
- бэкапы: `/data/backups`

## Возможности

- **Jobs (CRUD)**: создание/редактирование/удаление заданий бэкапа
- **Планировщик**: cron‑расписание (5 полей), `max_instances=1` (пропуск если предыдущий запуск не завершён)
- **Postgres**: `pg_dump` (plain/custom)
- **MongoDB**: `mongodump`
- **S3/MinIO**: рекурсивная выгрузка всех объектов бакета
- **Пост‑обработка**: автоматическое сжатие в `.tar.gz`, удаление исходников после успешного сжатия
- **Retention**: удаление старых бэкапов (по возрасту и/или по общей квоте)
- **Безопасность**: секреты шифруются в SQLite (Fernet), в API/UI возвращаются замаскированными

## API (основное)

- `GET /api/dashboard`
- `GET /api/jobs`
- `POST /api/jobs`
- `PUT /api/jobs/{id}`
- `DELETE /api/jobs/{id}`
- `GET /api/jobs/{id}/runs`
- `POST /api/jobs/{id}/run-now`
- `GET /api/runs/{run_id}/log`

## Примечания

- В контейнере используются утилиты `pg_dump` и `mongodump` (устанавливаются в `Dockerfile`).
- Cron поддерживается в формате **5 полей** (как в crontab): `min hour day month day_of_week`.
- Расписание cron считается в часовом поясе из `SCHEDULER_TZ` (по умолчанию `UTC`). Например, для запуска в 03:00 по Москве задайте `SCHEDULER_TZ=Europe/Moscow` и `"schedule_cron": "0 3 * * *"`.

## Примеры заданий (JSON)

### PostgreSQL

```json
{
  "name": "prod-postgres",
  "source_type": "postgres",
  "schedule_cron": "0 2 * * *",
  "destination_path": "prod",
  "enabled": true,
  "postgres": {
    "host": "postgres",
    "port": 5432,
    "database": "app",
    "user": "app",
    "password": "secret",
    "sslmode": "prefer",
    "format": "custom"
  }
}
```

### MongoDB

```json
{
  "name": "prod-mongo",
  "source_type": "mongo",
  "schedule_cron": "30 2 * * *",
  "destination_path": "prod",
  "enabled": true,
  "mongo": {
    "host": "mongo",
    "port": 27017,
    "database": "app",
    "user": "app",
    "password": "secret",
    "authSource": "admin"
  }
}
```

### S3 / MinIO

```json
{
  "name": "prod-minio",
  "source_type": "s3",
  "schedule_cron": "0 */6 * * *",
  "destination_path": "prod",
  "enabled": true,
  "s3": {
    "endpoint": "http://minio:9000",
    "access_key": "minioadmin",
    "secret_key": "minioadmin",
    "bucket": "backups",
    "region": "",
    "use_ssl": false,
    "path_style": true
  }
}
```

### Все источники одновременно (all)

```json
{
  "name": "prod-all",
  "source_type": "all",
  "schedule_cron": "0 3 * * *",
  "destination_path": "prod",
  "enabled": true,
  "postgres": { "host": "postgres", "port": 5432, "database": "app", "user": "app", "password": "secret", "sslmode": "prefer", "format": "custom" },
  "mongo": { "host": "mongo", "port": 27017, "database": "app", "user": "app", "password": "secret", "authSource": "admin" },
  "s3": { "endpoint": "http://minio:9000", "access_key": "minioadmin", "secret_key": "minioadmin", "bucket": "backups", "region": "", "use_ssl": false, "path_style": true }
}
```

