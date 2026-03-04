from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from backend.app.core.config import settings


_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def safe_slug(s: str) -> str:
    s = s.strip().replace(" ", "-")
    s = _SAFE.sub("_", s)
    return s[:80] or "job"


def make_run_dir(destination_path: str, job_name: str, ts: datetime | None = None) -> Path:
    ts = ts or datetime.utcnow()
    rel = Path(destination_path) / safe_slug(job_name) / ts.strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(settings.backup_root) / rel
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def dir_size_bytes(p: Path) -> int:
    if not p.exists():
        return 0
    if p.is_file():
        return p.stat().st_size
    total = 0
    for fp in p.rglob("*"):
        if fp.is_file():
            total += fp.stat().st_size
    return total

