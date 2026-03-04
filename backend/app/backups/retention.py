from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.app.backups.utils import dir_size_bytes


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def cleanup_job_dir(job_dir: Path, *, max_age_days: int | None, max_total_bytes: int | None) -> list[str]:
    """
    Deletes oldest run directories under job_dir according to policy.
    Returns a list of human-readable actions for logging.
    """
    actions: list[str] = []
    if not job_dir.exists():
        return actions

    run_dirs = [p for p in job_dir.iterdir() if p.is_dir()]
    run_dirs.sort(key=lambda p: p.stat().st_mtime)

    if max_age_days is not None:
        cutoff = _utcnow() - timedelta(days=max_age_days)
        for p in list(run_dirs):
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                sz = dir_size_bytes(p)
                shutil.rmtree(p, ignore_errors=True)
                actions.append(f"retention: removed old run dir {p} ({sz} bytes)")
                run_dirs.remove(p)

    if max_total_bytes is not None:
        sizes = [(p, dir_size_bytes(p)) for p in run_dirs]
        total = sum(sz for _, sz in sizes)
        for p, sz in sizes:
            if total <= max_total_bytes:
                break
            shutil.rmtree(p, ignore_errors=True)
            total -= sz
            actions.append(f"retention: removed to fit quota {p} ({sz} bytes)")

    return actions

