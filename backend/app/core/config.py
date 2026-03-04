from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="copycon-backuper", alias="APP_NAME")
    app_env: Literal["dev", "prod"] = Field(default="dev", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    db_path: str = Field(default="/data/app.db", alias="DB_PATH")
    log_dir: str = Field(default="/data/logs", alias="LOG_DIR")
    backup_root: str = Field(default="/data/backups", alias="BACKUP_ROOT")

    secrets_fernet_key: str = Field(alias="SECRETS_FERNET_KEY")

    max_concurrent_jobs: int = Field(default=2, alias="MAX_CONCURRENT_JOBS")
    run_log_max_chars: int = Field(default=20000, alias="RUN_LOG_MAX_CHARS")

    max_backup_age_days: Optional[int] = Field(default=30, alias="MAX_BACKUP_AGE_DAYS")
    max_backup_total_bytes: Optional[int] = Field(default=None, alias="MAX_BACKUP_TOTAL_BYTES")

    @field_validator("max_backup_age_days", "max_backup_total_bytes", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v):
        if v == "":
            return None
        return v

    def ensure_dirs(self) -> None:
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        Path(self.backup_root).mkdir(parents=True, exist_ok=True)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
