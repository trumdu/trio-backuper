from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from apscheduler.triggers.cron import CronTrigger

from backend.app.db.models import JobSourceType, RunStatus


def _validate_cron(expr: str) -> str:
    # APScheduler supports standard 5-field crontab here.
    CronTrigger.from_crontab(expr)
    return expr


def _validate_dest(dest: str) -> str:
    dest = dest.strip().strip("/").strip("\\")
    if not dest:
        raise ValueError("destination_path cannot be empty")
    if ".." in dest.replace("\\", "/").split("/"):
        raise ValueError("destination_path cannot contain '..'")
    return dest


class PostgresConfigIn(BaseModel):
    host: str
    port: int = 5432
    database: str
    user: str
    password: Optional[str] = None
    sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = "prefer"
    format: Literal["plain", "custom"] = "custom"


class MongoConfigIn(BaseModel):
    host: str
    port: int = 27017
    database: str
    user: Optional[str] = None
    password: Optional[str] = None
    authSource: str = "admin"


class S3ConfigIn(BaseModel):
    endpoint: str
    access_key: str
    secret_key: Optional[str] = None
    bucket: str
    region: Optional[str] = None
    use_ssl: bool = True
    path_style: bool = True
    verify_ssl: bool = True


class JobBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_type: JobSourceType
    schedule_cron: str
    destination_path: str
    enabled: bool = True

    postgres: Optional[PostgresConfigIn] = None
    mongo: Optional[MongoConfigIn] = None
    s3: Optional[S3ConfigIn] = None

    _cron_ok = field_validator("schedule_cron")(_validate_cron)
    _dest_ok = field_validator("destination_path")(_validate_dest)

    @field_validator("postgres", "mongo", "s3")
    @classmethod
    def _empty_dict_to_none(cls, v: Any):
        if v == {}:
            return None
        return v

    @model_validator(mode="after")
    def _validate_source_configs(self):
        st = self.source_type
        if st == JobSourceType.postgres and not self.postgres:
            raise ValueError("postgres config is required for source_type=postgres")
        if st == JobSourceType.mongo and not self.mongo:
            raise ValueError("mongo config is required for source_type=mongo")
        if st == JobSourceType.s3 and not self.s3:
            raise ValueError("s3 config is required for source_type=s3")
        if st == JobSourceType.all and (not self.postgres or not self.mongo or not self.s3):
            raise ValueError("postgres, mongo and s3 configs are required for source_type=all")
        return self


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    source_type: Optional[JobSourceType] = None
    schedule_cron: Optional[str] = None
    destination_path: Optional[str] = None
    enabled: Optional[bool] = None

    postgres: Optional[PostgresConfigIn] = None
    mongo: Optional[MongoConfigIn] = None
    s3: Optional[S3ConfigIn] = None

    @field_validator("schedule_cron")
    @classmethod
    def _cron_ok_update(cls, v: Optional[str]):
        if v is None:
            return v
        return _validate_cron(v)

    @field_validator("destination_path")
    @classmethod
    def _dest_ok_update(cls, v: Optional[str]):
        if v is None:
            return v
        return _validate_dest(v)


class JobOut(BaseModel):
    id: int
    name: str
    source_type: JobSourceType
    schedule_cron: str
    destination_path: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    last_run_status: Optional[RunStatus] = None

    from_config: Optional[bool] = None

    postgres: Optional[dict[str, Any]] = None
    mongo: Optional[dict[str, Any]] = None
    s3: Optional[dict[str, Any]] = None


class RunOut(BaseModel):
    id: int
    job_id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: RunStatus
    size_bytes: Optional[int] = None
    output_path: Optional[str] = None


class RunLogOut(BaseModel):
    id: int
    log_text: str = ""
    error_text: str = ""


class DashboardOut(BaseModel):
    total_jobs: int
    success_24h: int
    failed_24h: int
    disk_total_bytes: int
    disk_used_bytes: int
    disk_free_bytes: int
