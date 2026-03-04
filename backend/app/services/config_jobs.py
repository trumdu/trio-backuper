from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Job
from backend.app.schemas import JobCreate, JobUpdate
from backend.app.services.jobs_service import create_job, update_job

log = logging.getLogger(__name__)


def _normalize_jobs_payload(raw: Any) -> list[dict[str, Any]]:
    # Support:
    # - single job object (as in README examples)
    # - list of job objects
    # - {"jobs": [ ... ]}
    if isinstance(raw, dict) and "jobs" in raw:
        raw_jobs = raw["jobs"]
        if not isinstance(raw_jobs, list):
            raise ValueError('"jobs" must be a list')
        return [j for j in raw_jobs]
    if isinstance(raw, list):
        return [j for j in raw]
    if isinstance(raw, dict):
        return [raw]
    raise ValueError("config root must be an object, a list, or an object with 'jobs'")


def _find_existing_job_by_name(db: Session, name: str) -> Job | None:
    return db.scalars(select(Job).where(Job.name == name).limit(1)).first()


def sync_jobs_from_config_file(db: Session, config_path: str) -> dict[str, int]:
    """
    Reads jobs from config JSON file and upserts them into DB by name.
    If a job exists, it is updated to match config (secrets are preserved if empty/null in config).
    """
    p = Path(config_path)
    fallback_paths: list[Path] = []
    if not p.is_absolute():
        # When running in Docker, jobs config is typically stored in the mounted /data volume.
        fallback_paths.append(Path("/data") / p.name)

    candidate_paths = [p, *fallback_paths]
    chosen: Path | None = None
    for cp in candidate_paths:
        if cp.exists() and cp.is_file():
            chosen = cp
            break

    if not chosen:
        log.info("jobs_config_not_found", extra={"config_path": config_path, "candidates": [str(x) for x in candidate_paths]})
        return {"created": 0, "updated": 0}

    raw = json.loads(chosen.read_text(encoding="utf-8"))
    raw_jobs = _normalize_jobs_payload(raw)

    created = 0
    updated = 0

    for idx, job_raw in enumerate(raw_jobs):
        if not isinstance(job_raw, dict):
            raise ValueError(f"job[{idx}] must be an object")

        job_create = JobCreate.model_validate(job_raw)
        existing = _find_existing_job_by_name(db, job_create.name)
        if not existing:
            create_job(db, job_create)
            created += 1
        else:
            job_update = JobUpdate(**job_create.model_dump())
            update_job(db, existing, job_update)
            updated += 1

    log.info("jobs_config_synced", extra={"path": str(chosen), "created": created, "updated": updated})
    return {"created": created, "updated": updated}

