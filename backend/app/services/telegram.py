from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from backend.app.core.config import settings
from backend.app.db.models import RunStatus

log = logging.getLogger(__name__)

_TELEGRAM_MAX_TEXT = 4096
_HTTP_TIMEOUT = 10.0


@dataclass(frozen=True)
class RunNotifyContext:
    job_id: int
    job_name: str
    run_id: int
    status: RunStatus
    size_bytes: int | None
    output_path: str | None
    error_text: str | None
    reason: str


def _is_configured() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def _should_notify(ctx: RunNotifyContext) -> bool:
    if not _is_configured():
        return False
    if ctx.status == RunStatus.success:
        return settings.telegram_notify_on_success
    if ctx.status == RunStatus.failed:
        return settings.telegram_notify_on_failure
    return False


def _format_message(ctx: RunNotifyContext) -> str:
    if ctx.status == RunStatus.success:
        prefix = "✅ Backup success"
        lines = [
            f"{prefix}: {ctx.job_name}",
            f"run_id={ctx.run_id} reason={ctx.reason}",
        ]
        if ctx.size_bytes is not None:
            lines.append(f"size_bytes={ctx.size_bytes}")
        if ctx.output_path:
            lines.append(f"path={ctx.output_path}")
    else:
        prefix = "❌ Backup failed"
        lines = [
            f"{prefix}: {ctx.job_name}",
            f"run_id={ctx.run_id} reason={ctx.reason}",
        ]
        if ctx.error_text:
            lines.append(f"error={ctx.error_text}")

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


async def notify_run_finished(ctx: RunNotifyContext) -> str | None:
    if not _should_notify(ctx):
        return None

    text = _format_message(ctx)
    try:
        await _send_message(text)
        log.info(
            "telegram_notify_sent",
            extra={"job_id": ctx.job_id, "run_id": ctx.run_id, "status": ctx.status.value},
        )
        return "telegram: sent"
    except Exception as exc:
        log.warning(
            "telegram_notify_failed",
            extra={"job_id": ctx.job_id, "run_id": ctx.run_id, "error": str(exc)},
        )
        return f"telegram: failed: {exc}"
