from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.app.backups.runner import enqueue_run
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.schemas import JobCreate, JobOut, JobUpdate, RunLogOut, RunOut
from backend.app.scheduler.scheduler import scheduler_manager
from backend.app.services.config_jobs import sync_jobs_from_config_file
from backend.app.services.jobs_service import (
    delete_job,
    get_job_model,
    job_to_out,
    list_jobs,
    update_job,
)
from backend.app.services.runs_service import get_run_log, list_runs_for_job

router = APIRouter()


@router.post("/jobs/sync-from-config")
def jobs_sync_from_config(db: Session = Depends(get_db)) -> dict:
    try:
        result = sync_jobs_from_config_file(db, settings.config_path)
        scheduler_manager.sync_from_db()
        return {"synced": True, **result}
    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs", response_model=list[JobOut])
def jobs_list(db: Session = Depends(get_db)) -> list[JobOut]:
    return list_jobs(db)


@router.post("/jobs", response_model=JobOut)
def jobs_create(payload: JobCreate, db: Session = Depends(get_db)) -> JobOut:
    raise HTTPException(
        status_code=405,
        detail="Job creation via API is disabled. Add jobs via config.json and call /api/jobs/sync-from-config (or restart the app).",
    )


@router.get("/jobs/{job_id}", response_model=JobOut)
def jobs_get(job_id: int, db: Session = Depends(get_db)) -> JobOut:
    job = get_job_model(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_out(db, job)


@router.put("/jobs/{job_id}", response_model=JobOut)
def jobs_update(job_id: int, payload: JobUpdate, db: Session = Depends(get_db)) -> JobOut:
    job = get_job_model(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    out = update_job(db, job, payload)
    if out.enabled:
        scheduler_manager.upsert_job(out.id, out.schedule_cron)
    else:
        scheduler_manager.remove_job(out.id)
    return out


@router.delete("/jobs/{job_id}")
def jobs_delete(job_id: int, db: Session = Depends(get_db)) -> dict:
    job = get_job_model(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    scheduler_manager.remove_job(job_id)
    delete_job(db, job)
    return {"deleted": True}


@router.get("/jobs/{job_id}/runs", response_model=list[RunOut])
def job_runs(job_id: int, db: Session = Depends(get_db)) -> list[RunOut]:
    return list_runs_for_job(db, job_id)


@router.post("/jobs/{job_id}/run-now")
async def run_now(job_id: int, db: Session = Depends(get_db)) -> dict:
    job = get_job_model(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await enqueue_run(job_id, reason="manual")
    return {"enqueued": True}


@router.get("/runs/{run_id}/log", response_model=RunLogOut)
def run_log(run_id: int, db: Session = Depends(get_db)) -> RunLogOut:
    out = get_run_log(db, run_id)
    if not out:
        raise HTTPException(status_code=404, detail="Run not found")
    return out

