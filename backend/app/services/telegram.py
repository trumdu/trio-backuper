from __future__ import annotations

import logging

import httpx

from backend.app.core.config import settings
from backend.app.db.models import BackupRun, Job, RunStatus

log = logging.getLogger(__name__)

_TELEGRAM_MAX_TEXT = 4096
_HTTP_TIMEOUT = 10.0


def _is_configured() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def _should_notify(run: BackupRun) -> bool:
    if not _is_configured():
        return False
    if run.status == RunStatus.success:
        return settings.telegram_notify_on_success
    if run.status == RunStatus.failed:
        return settings.telegram_notify_on_failure
    return False


def _format_message(*, job: Job, run: BackupRun, reason: str) -> str:
    if run.status == RunStatus.success:
        prefix = "✅ Backup success"
        lines = [
            f"{prefix}: {job.name}",
            f"run_id={run.id} reason={reason}",
        ]
        if run.size_bytes is not None:
            lines.append(f"size_bytes={run.size_bytes}")
        if run.output_path:
            lines.append(f"path={run.output_path}")
    else:
        prefix = "❌ Backup failed"
        lines = [
            f"{prefix}: {job.name}",
            f"run_id={run.id} reason={reason}",
        ]
        if run.error_text:
            lines.append(f"error={run.error_text}")

    text = "\n".join(lines)
    if len(text) <= _TELEGRAM_MAX_TEXT:
        return text
    return text[: _TELEGRAM_MAX_TEXT - 3] + "..."


def _send_url() -> str:
    base = settings.telegram_api_url.rstrip("/")
    return f"{base}/bot{settings.telegram_bot_token}/sendMessage"


async def _send_message(text: str) -> None:
    url = _send_url()
    payload = {"chat_id": settings.telegram_chat_id, "text": text}
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()


async def notify_run_finished(*, job: Job, run: BackupRun, reason: str) -> None:
    if not _should_notify(run):
        return

    text = _format_message(job=job, run=run, reason=reason)
    try:
        await _send_message(text)
        log.info(
            "telegram_notify_sent",
            extra={"job_id": job.id, "run_id": run.id, "status": run.status.value},
        )
    except Exception as exc:
        log.warning(
            "telegram_notify_failed",
            extra={"job_id": job.id, "run_id": run.id, "error": str(exc)},
        )
