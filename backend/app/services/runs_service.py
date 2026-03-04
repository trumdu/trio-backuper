from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import BackupRun, Job, RunStatus
from backend.app.schemas import RunLogOut, RunOut


def list_runs_for_job(db: Session, job_id: int, limit: int = 50) -> list[RunOut]:
    runs = (
        db.scalars(
            select(BackupRun).where(BackupRun.job_id == job_id).order_by(BackupRun.started_at.desc()).limit(limit)
        )
        .all()
    )
    return [
        RunOut(
            id=r.id,
            job_id=r.job_id,
            started_at=r.started_at,
            finished_at=r.finished_at,
            status=r.status,
            size_bytes=r.size_bytes,
            output_path=r.output_path,
        )
        for r in runs
    ]


def get_run_log(db: Session, run_id: int) -> RunLogOut | None:
    run = db.get(BackupRun, run_id)
    if not run:
        return None
    return RunLogOut(id=run.id, log_text=run.log_text or "", error_text=run.error_text or "")


def count_runs_status_last_24h(db: Session, status: RunStatus) -> int:
    since = datetime.utcnow() - timedelta(hours=24)
    q = select(func.count()).select_from(BackupRun).where(BackupRun.started_at >= since, BackupRun.status == status)
    return int(db.scalar(q) or 0)


def get_job(db: Session, job_id: int) -> Job | None:
    return db.get(Job, job_id)
