from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from backend.app.backups.compress import to_targz
from backend.app.backups.mongo import backup_mongodump, test_connection as mongo_test_connection
from backend.app.backups.postgres import backup_pg_dump, test_connection as postgres_test_connection
from backend.app.backups.retention import cleanup_job_dir
from backend.app.backups.s3 import backup_bucket, test_connection as s3_test_connection
from backend.app.backups.utils import dir_size_bytes, make_run_dir, safe_slug
from backend.app.core.config import settings
from backend.app.db.models import BackupRun, Job, JobSourceType, RunStatus
from backend.app.db.session import SessionLocal
from backend.app.services.runtime_config import get_mongo_config, get_postgres_config, get_s3_config

log = logging.getLogger(__name__)

_sema = asyncio.Semaphore(settings.max_concurrent_jobs)
_tasks: set[asyncio.Task] = set()


def _truncate(s: str) -> str:
    if len(s) <= settings.run_log_max_chars:
        return s
    return s[-settings.run_log_max_chars :]


async def enqueue_run(job_id: int, *, reason: str = "manual") -> dict[str, Any]:
    task = asyncio.create_task(_run_job(job_id, reason=reason))
    _tasks.add(task)
    task.add_done_callback(lambda t: _tasks.discard(t))
    return {"enqueued": True}


async def shutdown_running_tasks() -> None:
    for t in list(_tasks):
        t.cancel()
    await asyncio.gather(*list(_tasks), return_exceptions=True)
    _tasks.clear()


async def _run_job(job_id: int, *, reason: str) -> None:
    async with _sema:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if not job or not job.enabled:
                return

            running = db.scalar(
                select(BackupRun.id).where(BackupRun.job_id == job_id, BackupRun.status == RunStatus.running).limit(1)
            )
            if running:
                log.info("job_skip_already_running", extra={"job_id": job_id, "reason": reason})
                return

            run = BackupRun(
                job_id=job_id,
                started_at=datetime.utcnow(),
                status=RunStatus.running,
                log_text=f"reason={reason}\n",
            )
            db.add(run)
            db.commit()
            db.refresh(run)

            try:
                run_dir = make_run_dir(job.destination_path, job.name, ts=run.started_at)
                actions: list[str] = [f"run_dir={run_dir}\n", f"source_type={job.source_type}\n"]

                if job.source_type == JobSourceType.postgres:
                    out_path, size, log_text = await _do_postgres(job, run_dir)
                elif job.source_type == JobSourceType.mongo:
                    out_path, size, log_text = await _do_mongo(job, run_dir)
                elif job.source_type == JobSourceType.s3:
                    out_path, size, log_text = await _do_s3(job, run_dir)
                elif job.source_type == JobSourceType.all:
                    out_path, size, log_text = await _do_all(job, run_dir)
                else:
                    raise RuntimeError(f"Unknown source_type: {job.source_type}")

                actions.append(log_text + "\n")

                # retention: apply within job folder
                job_dir = run_dir.parent
                actions.extend(
                    cleanup_job_dir(
                        job_dir,
                        max_age_days=settings.max_backup_age_days,
                        max_total_bytes=settings.max_backup_total_bytes,
                    )
                )

                run.finished_at = datetime.utcnow()
                run.status = RunStatus.success
                run.size_bytes = int(size)
                run.output_path = str(out_path)
                run.log_text = _truncate((run.log_text or "") + "\n".join(actions))
                run.error_text = None
                db.add(run)
                db.commit()
                log.info("job_run_success", extra={"job_id": job_id, "run_id": run.id, "out": str(out_path)})
            except asyncio.CancelledError:
                run.finished_at = datetime.utcnow()
                run.status = RunStatus.failed
                run.error_text = _truncate((run.error_text or "") + "\nCancelled\n")
                db.add(run)
                db.commit()
                raise
            except Exception as e:
                run.finished_at = datetime.utcnow()
                run.status = RunStatus.failed
                run.error_text = _truncate(str(e))
                run.log_text = _truncate(run.log_text or "")
                db.add(run)
                db.commit()
                log.exception("job_run_failed", extra={"job_id": job_id, "run_id": run.id})


async def _do_postgres(job: Job, run_dir: Path) -> tuple[Path, int, str]:
    cfg = get_postgres_config(job)
    if not cfg:
        raise RuntimeError("Postgres config missing")
    raw_path, src_log = await backup_pg_dump(cfg, out_dir=run_dir)
    archive = run_dir / "postgres.tar.gz"
    to_targz(raw_path, archive)
    try:
        raw_path.unlink(missing_ok=True)
    except Exception:
        pass
    return archive, archive.stat().st_size, src_log


async def _do_mongo(job: Job, run_dir: Path) -> tuple[Path, int, str]:
    cfg = get_mongo_config(job)
    if not cfg:
        raise RuntimeError("Mongo config missing")
    raw_dir, src_log = await backup_mongodump(cfg, out_dir=run_dir)
    archive = run_dir / "mongo.tar.gz"
    to_targz(raw_dir, archive)
    shutil.rmtree(raw_dir, ignore_errors=True)
    return archive, archive.stat().st_size, src_log


async def _do_s3(job: Job, run_dir: Path) -> tuple[Path, int, str]:
    cfg = get_s3_config(job)
    if not cfg:
        raise RuntimeError("S3 config missing")
    raw_dir, src_log = await backup_bucket(cfg, out_dir=run_dir)
    archive = run_dir / "s3.tar.gz"
    to_targz(raw_dir, archive)
    shutil.rmtree(raw_dir, ignore_errors=True)
    return archive, archive.stat().st_size, src_log


async def _do_all(job: Job, run_dir: Path) -> tuple[Path, int, str]:
    pg_cfg = get_postgres_config(job)
    mongo_cfg = get_mongo_config(job)
    s3_cfg = get_s3_config(job)

    # Проверка доступности всех источников параллельно; только после успеха — запуск бэкапов.
    check_tasks: list[asyncio.Task] = []
    names: list[str] = []
    if pg_cfg:
        check_tasks.append(asyncio.create_task(postgres_test_connection(pg_cfg)))
        names.append("postgres")
    if mongo_cfg:
        check_tasks.append(asyncio.create_task(mongo_test_connection(mongo_cfg)))
        names.append("mongo")
    if s3_cfg:
        check_tasks.append(asyncio.create_task(s3_test_connection(s3_cfg)))
        names.append("s3")

    if not check_tasks:
        raise RuntimeError("No configs provided for source_type=all")

    results = await asyncio.gather(*check_tasks, return_exceptions=True)
    failures: list[str] = []
    for name, r in zip(names, results):
        if isinstance(r, Exception):
            failures.append(f"{name}: {r!s}")
    if failures:
        raise RuntimeError("Pre-check failed: " + "; ".join(failures))

    # Все проверки прошли — параллельный запуск бэкапов.
    pre_check_log = "pre_check_ok: " + ", ".join(names)
    tasks: list[asyncio.Task] = []
    logs: list[str] = []
    sizes: int = 0

    async def _wrap(name: str, coro):
        nonlocal sizes
        p, sz, lg = await coro
        sizes += int(sz)
        logs.append(f"[{name}] {lg}")
        return p

    if pg_cfg:
        tasks.append(asyncio.create_task(_wrap("postgres", _do_postgres(job, run_dir))))
    if mongo_cfg:
        tasks.append(asyncio.create_task(_wrap("mongo", _do_mongo(job, run_dir))))
    if s3_cfg:
        tasks.append(asyncio.create_task(_wrap("s3", _do_s3(job, run_dir))))

    await asyncio.gather(*tasks)
    return run_dir, int(sizes), pre_check_log + "\n" + "\n".join(logs)

