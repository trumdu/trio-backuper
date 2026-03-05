from __future__ import annotations

import asyncio
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from backend.app.backups.runner import enqueue_run, shutdown_running_tasks
from backend.app.core.config import settings
from backend.app.db.models import Job
from backend.app.db.session import SessionLocal

log = logging.getLogger(__name__)


def _scheduler_timezone():
    try:
        return ZoneInfo(settings.scheduler_tz)
    except Exception:
        return ZoneInfo("UTC")


class SchedulerManager:
    def __init__(self) -> None:
        self._tz = _scheduler_timezone()
        self._scheduler = AsyncIOScheduler(timezone=self._tz)
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._scheduler.start()
        self._started = True
        self.sync_from_db()
        log.info("scheduler_started", extra={"timezone": settings.scheduler_tz})

    async def shutdown(self) -> None:
        if not self._started:
            return
        self._scheduler.shutdown(wait=False)
        await shutdown_running_tasks()
        self._started = False
        log.info("scheduler_stopped")

    def sync_from_db(self) -> None:
        with SessionLocal() as db:
            jobs = db.scalars(select(Job).where(Job.enabled == True)).all()  # noqa: E712
            enabled_ids = {j.id for j in jobs}
            for job in jobs:
                self.upsert_job(job.id, job.schedule_cron)

        # Unschedule jobs that are no longer enabled / removed.
        if not self._started:
            return
        try:
            for aps_job in self._scheduler.get_jobs():
                jid = str(getattr(aps_job, "id", "") or "")
                if not jid.startswith("job:"):
                    continue
                try:
                    job_id = int(jid.split(":", 1)[1])
                except Exception:
                    continue
                if job_id not in enabled_ids:
                    try:
                        self._scheduler.remove_job(jid)
                    except Exception:
                        pass
        except Exception:
            # best-effort cleanup
            pass

    def upsert_job(self, job_id: int, cron_expr: str) -> None:
        if not self._started:
            return
        trigger = CronTrigger.from_crontab(cron_expr, timezone=self._tz)
        aps_id = f"job:{job_id}"

        async def _fire():
            # AsyncIOScheduler умеет выполнять корутины, дополнительный create_task не нужен.
            await enqueue_run(job_id, reason="schedule")

        job = self._scheduler.add_job(
            _fire,
            trigger=trigger,
            id=aps_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )
        next_run = getattr(job, "next_run_time", None)
        log.info(
            "job_scheduled",
            extra={
                "job_id": job_id,
                "cron": cron_expr,
                "timezone": settings.scheduler_tz,
                "next_run": str(next_run) if next_run else None,
            },
        )

    def remove_job(self, job_id: int) -> None:
        if not self._started:
            return
        aps_id = f"job:{job_id}"
        try:
            self._scheduler.remove_job(aps_id)
            log.info("job_unscheduled", extra={"job_id": job_id})
        except Exception:
            # ignore if not exists
            pass


scheduler_manager = SchedulerManager()
