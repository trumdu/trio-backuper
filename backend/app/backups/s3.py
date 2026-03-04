from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Optional

import boto3
from botocore.config import Config

from backend.app.backups.retry import retry_async
from backend.app.backups.base import BackupSource, RawBackup


def _endpoint_url(cfg: dict[str, Any]) -> str:
    ep = str(cfg["endpoint"]).strip()
    if ep.startswith("http://") or ep.startswith("https://"):
        return ep
    scheme = "https" if cfg.get("use_ssl", True) else "http"
    return f"{scheme}://{ep}"


def _client(cfg: dict[str, Any]):
    addressing_style = "path" if bool(cfg.get("path_style", True)) else "virtual"
    c = Config(
        s3={"addressing_style": addressing_style},
        retries={"max_attempts": 5, "mode": "standard"},
        connect_timeout=5,
        read_timeout=300,
    )
    return boto3.client(
        "s3",
        endpoint_url=_endpoint_url(cfg),
        aws_access_key_id=str(cfg["access_key"]),
        aws_secret_access_key=str(cfg.get("secret_key") or ""),
        region_name=str(cfg["region"]) if cfg.get("region") else None,
        config=c,
        verify=True,
    )


async def test_connection(cfg: dict[str, Any]) -> None:
    def _head():
        cli = _client(cfg)
        cli.head_bucket(Bucket=str(cfg["bucket"]))

    await asyncio.to_thread(_head)


async def backup_bucket(
    cfg: dict[str, Any],
    *,
    out_dir: Path,
) -> tuple[Path, str]:
    """
    Returns (raw_download_dir, log_text)
    """
    await retry_async(lambda: test_connection(cfg), attempts=3, base_delay_s=1.0)

    bucket = str(cfg["bucket"])
    target_dir = out_dir / "s3"
    target_dir.mkdir(parents=True, exist_ok=True)

    def _download_all() -> str:
        cli = _client(cfg)
        paginator = cli.get_paginator("list_objects_v2")
        downloaded = 0
        bytes_written = 0

        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []) or []:
                key = obj["Key"]
                if key.endswith("/"):
                    continue
                dst = target_dir / key
                dst.parent.mkdir(parents=True, exist_ok=True)
                with open(dst, "wb") as f:
                    cli.download_fileobj(bucket, key, f)
                downloaded += 1
                try:
                    bytes_written += dst.stat().st_size
                except OSError:
                    pass

        return f"s3 download ok: objects={downloaded} bytes={bytes_written} dir={target_dir}"

    log_text = await asyncio.to_thread(_download_all)
    return target_dir, log_text


class S3Source(BackupSource):
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg

    @property
    def name(self) -> str:
        return "s3"

    async def test_connection(self) -> None:
        await test_connection(self.cfg)

    async def backup_raw(self, out_dir: Path) -> RawBackup:
        p, log_text = await backup_bucket(self.cfg, out_dir=out_dir)
        return RawBackup(path=p, log_text=log_text)

    def redact(self) -> dict[str, Any]:
        c = dict(self.cfg)
        if "secret_key" in c and c["secret_key"]:
            c["secret_key"] = "********"
        return c

