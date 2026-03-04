from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import BackupRun, Job, JobSourceType
from backend.app.schemas import JobCreate, JobOut, JobUpdate
from backend.app.services.secrets_json import (
    dumps_with_encrypted_fields,
    loads_masked,
)


POSTGRES_SECRET_FIELDS = ("password",)
MONGO_SECRET_FIELDS = ("password",)
S3_SECRET_FIELDS = ("secret_key",)


def _json_load(s: str | None) -> dict[str, Any] | None:
    if not s:
        return None
    return json.loads(s)


def _merge_config_keep_secrets(existing_json: str | None, new_cfg: dict[str, Any] | None, secret_fields: tuple[str, ...]) -> str | None:
    if new_cfg is None:
        return existing_json

    existing = _json_load(existing_json) or {}
    secret_fields_set = set(secret_fields)

    merged: dict[str, Any] = dict(existing)
    for k, v in new_cfg.items():
        if k in secret_fields_set and (v is None or v == ""):
            # keep existing (encrypted token)
            continue
        merged[k] = v

    # encrypt secret fields for storage
    return dumps_with_encrypted_fields(merged, secret_fields)


def job_to_out(db: Session, job: Job) -> JobOut:
    last_status = db.scalar(
        select(BackupRun.status).where(BackupRun.job_id == job.id).order_by(BackupRun.started_at.desc()).limit(1)
    )
    return JobOut(
        id=job.id,
        name=job.name,
        source_type=job.source_type,
        schedule_cron=job.schedule_cron,
        destination_path=job.destination_path,
        enabled=job.enabled,
        created_at=job.created_at,
        updated_at=job.updated_at,
        last_run_status=last_status,
        postgres=loads_masked(job.postgres_config_json, POSTGRES_SECRET_FIELDS),
        mongo=loads_masked(job.mongo_config_json, MONGO_SECRET_FIELDS),
        s3=loads_masked(job.s3_config_json, S3_SECRET_FIELDS),
    )


def list_jobs(db: Session) -> list[JobOut]:
    jobs = db.scalars(select(Job).order_by(Job.id.asc())).all()
    return [job_to_out(db, j) for j in jobs]


def get_job(db: Session, job_id: int) -> JobOut | None:
    job = db.get(Job, job_id)
    if not job:
        return None
    return job_to_out(db, job)


def get_job_model(db: Session, job_id: int) -> Job | None:
    return db.get(Job, job_id)


def create_job(db: Session, payload: JobCreate) -> JobOut:
    job = Job(
        name=payload.name,
        source_type=payload.source_type,
        schedule_cron=payload.schedule_cron,
        destination_path=payload.destination_path,
        enabled=payload.enabled,
        postgres_config_json=dumps_with_encrypted_fields(payload.postgres.model_dump(), POSTGRES_SECRET_FIELDS)
        if payload.postgres
        else None,
        mongo_config_json=dumps_with_encrypted_fields(payload.mongo.model_dump(), MONGO_SECRET_FIELDS) if payload.mongo else None,
        s3_config_json=dumps_with_encrypted_fields(payload.s3.model_dump(), S3_SECRET_FIELDS) if payload.s3 else None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job_to_out(db, job)


def update_job(db: Session, job: Job, payload: JobUpdate) -> JobOut:
    data = payload.model_dump(exclude_unset=True)

    if "name" in data:
        job.name = data["name"]
    if "source_type" in data and data["source_type"] is not None:
        job.source_type = JobSourceType(data["source_type"])
    if "schedule_cron" in data and data["schedule_cron"] is not None:
        job.schedule_cron = data["schedule_cron"]
    if "destination_path" in data and data["destination_path"] is not None:
        job.destination_path = data["destination_path"]
    if "enabled" in data and data["enabled"] is not None:
        job.enabled = bool(data["enabled"])

    if "postgres" in data:
        job.postgres_config_json = _merge_config_keep_secrets(
            job.postgres_config_json, data.get("postgres"), POSTGRES_SECRET_FIELDS
        )
    if "mongo" in data:
        job.mongo_config_json = _merge_config_keep_secrets(job.mongo_config_json, data.get("mongo"), MONGO_SECRET_FIELDS)
    if "s3" in data:
        job.s3_config_json = _merge_config_keep_secrets(job.s3_config_json, data.get("s3"), S3_SECRET_FIELDS)

    job.updated_at = datetime.utcnow()

    db.add(job)
    db.commit()
    db.refresh(job)
    return job_to_out(db, job)


def delete_job(db: Session, job: Job) -> None:
    db.delete(job)
    db.commit()


def count_jobs(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(Job)) or 0)
