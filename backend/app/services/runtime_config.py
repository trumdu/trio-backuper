from __future__ import annotations

from typing import Any

from backend.app.db.models import Job
from backend.app.services.secrets_json import loads_with_decrypted_fields
from backend.app.services.jobs_service import POSTGRES_SECRET_FIELDS, MONGO_SECRET_FIELDS, S3_SECRET_FIELDS


def get_postgres_config(job: Job) -> dict[str, Any] | None:
    return loads_with_decrypted_fields(job.postgres_config_json, POSTGRES_SECRET_FIELDS)


def get_mongo_config(job: Job) -> dict[str, Any] | None:
    return loads_with_decrypted_fields(job.mongo_config_json, MONGO_SECRET_FIELDS)


def get_s3_config(job: Job) -> dict[str, Any] | None:
    return loads_with_decrypted_fields(job.s3_config_json, S3_SECRET_FIELDS)

