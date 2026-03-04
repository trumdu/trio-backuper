from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import psycopg

from backend.app.backups.retry import retry_async
from backend.app.backups.base import BackupSource, RawBackup


async def test_connection(cfg: dict[str, Any], *, timeout_s: float = 5.0) -> None:
    def _conn():
        return psycopg.connect(
            host=cfg["host"],
            port=int(cfg.get("port", 5432)),
            dbname=cfg["database"],
            user=cfg["user"],
            password=cfg.get("password") or "",
            connect_timeout=int(timeout_s),
            sslmode=cfg.get("sslmode", "prefer"),
        )

    def _ping():
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

    await asyncio.to_thread(_ping)


async def backup_pg_dump(
    cfg: dict[str, Any],
    *,
    out_dir: Path,
    timeout_s: float = 60 * 60,
) -> tuple[Path, str]:
    """
    Returns (raw_dump_path, log_text)
    """
    await retry_async(lambda: test_connection(cfg), attempts=3, base_delay_s=1.0)

    fmt = cfg.get("format", "custom")
    ext = ".dump" if fmt == "custom" else ".sql"
    out_path = out_dir / f"postgres{ext}"

    cmd = [
        "pg_dump",
        "-h",
        str(cfg["host"]),
        "-p",
        str(int(cfg.get("port", 5432))),
        "-U",
        str(cfg["user"]),
        "-d",
        str(cfg["database"]),
        "-f",
        str(out_path),
    ]
    if fmt == "custom":
        cmd.append("-Fc")

    env = os.environ.copy()
    if cfg.get("password"):
        env["PGPASSWORD"] = str(cfg["password"])
    if cfg.get("sslmode"):
        env["PGSSLMODE"] = str(cfg["sslmode"])

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
        log = [f"cmd: {' '.join(cmd)}\n"]
        if stdout_b:
            log.append(stdout_b.decode("utf-8", errors="replace"))
        if stderr_b:
            log.append(stderr_b.decode("utf-8", errors="replace"))
        log_text = "".join(log).strip()

        if rc != 0:
            raise RuntimeError(f"pg_dump failed (code {rc}). Output:\n{log_text}")

        return out_path, (log_text or "pg_dump ok")

    return await retry_async(_run_once, attempts=3, base_delay_s=2.0)


class PostgresSource(BackupSource):
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg

    @property
    def name(self) -> str:
        return "postgres"

    async def test_connection(self) -> None:
        await test_connection(self.cfg)

    async def backup_raw(self, out_dir: Path) -> RawBackup:
        p, log_text = await backup_pg_dump(self.cfg, out_dir=out_dir)
        return RawBackup(path=p, log_text=log_text)

    def redact(self) -> dict[str, Any]:
        c = dict(self.cfg)
        if "password" in c and c["password"]:
            c["password"] = "********"
        return c

