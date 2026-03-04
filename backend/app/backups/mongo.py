from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from pymongo import MongoClient

from backend.app.backups.retry import retry_async
from backend.app.backups.base import BackupSource, RawBackup


async def test_connection(cfg: dict[str, Any], *, timeout_s: float = 5.0) -> None:
    def _ping():
        uri = f"mongodb://{cfg['host']}:{int(cfg.get('port', 27017))}"
        kwargs: dict[str, Any] = {"serverSelectionTimeoutMS": int(timeout_s * 1000)}
        if cfg.get("user"):
            kwargs["username"] = cfg.get("user")
        if cfg.get("password"):
            kwargs["password"] = cfg.get("password")
        if cfg.get("authSource"):
            kwargs["authSource"] = cfg.get("authSource")
        with MongoClient(uri, **kwargs) as client:
            client.admin.command("ping")

    await asyncio.to_thread(_ping)


async def backup_mongodump(
    cfg: dict[str, Any],
    *,
    out_dir: Path,
    timeout_s: float = 60 * 60,
) -> tuple[Path, str]:
    """
    Returns (raw_dump_dir, log_text)
    """
    await retry_async(lambda: test_connection(cfg), attempts=3, base_delay_s=1.0)

    dump_dir = out_dir / "mongo"
    dump_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "mongodump",
        "--host",
        str(cfg["host"]),
        "--port",
        str(int(cfg.get("port", 27017))),
        "--db",
        str(cfg["database"]),
        "--out",
        str(dump_dir),
    ]
    if cfg.get("user"):
        cmd += ["--username", str(cfg["user"])]
    if cfg.get("password"):
        cmd += ["--password", str(cfg["password"])]
    if cfg.get("authSource"):
        cmd += ["--authenticationDatabase", str(cfg.get("authSource"))]

    # For logging, redact password
    redacted = [("********" if x == str(cfg.get("password")) else x) for x in cmd]

    env = os.environ.copy()

    async def _run_once() -> tuple[Path, str]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.CancelledError:
            proc.kill()
            raise
        except asyncio.TimeoutError:
            proc.kill()
            raise

        rc = proc.returncode or 0
        log = [f"cmd: {' '.join(redacted)}\n"]
        if stdout_b:
            log.append(stdout_b.decode("utf-8", errors="replace"))
        if stderr_b:
            log.append(stderr_b.decode("utf-8", errors="replace"))
        log_text = "".join(log).strip()

        if rc != 0:
            raise RuntimeError(f"mongodump failed (code {rc}). Output:\n{log_text}")

        return dump_dir, (log_text or "mongodump ok")

    return await retry_async(_run_once, attempts=3, base_delay_s=2.0)


class MongoSource(BackupSource):
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg

    @property
    def name(self) -> str:
        return "mongo"

    async def test_connection(self) -> None:
        await test_connection(self.cfg)

    async def backup_raw(self, out_dir: Path) -> RawBackup:
        p, log_text = await backup_mongodump(self.cfg, out_dir=out_dir)
        return RawBackup(path=p, log_text=log_text)

    def redact(self) -> dict[str, Any]:
        c = dict(self.cfg)
        if "password" in c and c["password"]:
            c["password"] = "********"
        return c
