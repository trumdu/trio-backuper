from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.schemas import DashboardOut
from backend.app.services.jobs_service import count_jobs
from backend.app.services.runs_service import count_runs_status_last_24h
from backend.app.db.models import RunStatus

router = APIRouter()


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)) -> DashboardOut:
    du = shutil.disk_usage(settings.backup_root)
    return DashboardOut(
        total_jobs=count_jobs(db),
        success_24h=count_runs_status_last_24h(db, RunStatus.success),
        failed_24h=count_runs_status_last_24h(db, RunStatus.failed),
        disk_total_bytes=int(du.total),
        disk_used_bytes=int(du.used),
        disk_free_bytes=int(du.free),
    )

