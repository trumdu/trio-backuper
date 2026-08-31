import importlib
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from cryptography.fernet import Fernet

from backend.app.db.models import BackupRun, Job, JobSourceType, RunStatus


def _reload_telegram(monkeypatch, **env_overrides):
    defaults = {
        "SECRETS_FERNET_KEY": Fernet.generate_key().decode("utf-8"),
        "TELEGRAM_BOT_TOKEN": "123:ABC",
        "TELEGRAM_API_URL": "https://tg.example.com",
        "TELEGRAM_CHAT_ID": "-1001",
        "TELEGRAM_NOTIFY_ON_FAILURE": "true",
        "TELEGRAM_NOTIFY_ON_SUCCESS": "false",
    }
    defaults.update(env_overrides)
    for key, value in defaults.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    for m in ["backend.app.core.config", "backend.app.services.telegram"]:
        sys.modules.pop(m, None)

    import backend.app.services.telegram as telegram

    importlib.reload(telegram)
    return telegram


def _make_job(**kwargs) -> Job:
    job = Job(
        name=kwargs.get("name", "test-job"),
        source_type=JobSourceType.postgres,
        schedule_cron="0 2 * * *",
        destination_path="default",
        enabled=True,
    )
    job.id = kwargs.get("id", 1)
    return job


def _make_run(**kwargs) -> BackupRun:
    run = BackupRun(
        job_id=kwargs.get("job_id", 1),
        started_at=datetime.utcnow(),
        status=kwargs.get("status", RunStatus.success),
        size_bytes=kwargs.get("size_bytes"),
        output_path=kwargs.get("output_path"),
        error_text=kwargs.get("error_text"),
    )
    run.id = kwargs.get("id", 42)
    return run


@pytest.mark.asyncio
async def test_send_message_uses_correct_url_and_payload(monkeypatch):
    telegram = _reload_telegram(monkeypatch)
    job = _make_job()
    run = _make_run(status=RunStatus.failed, error_text="disk full")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_post = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.app.services.telegram.httpx.AsyncClient", return_value=mock_client):
        await telegram.notify_run_finished(job=job, run=run, reason="manual")

    mock_post.assert_awaited_once()
    call_args = mock_post.await_args
    assert call_args.args[0] == "https://tg.example.com/bot123:ABC/sendMessage"
    assert call_args.kwargs["json"]["chat_id"] == "-1001"
    assert "❌ Backup failed" in call_args.kwargs["json"]["text"]
    assert "disk full" in call_args.kwargs["json"]["text"]


@pytest.mark.asyncio
async def test_skips_when_token_or_chat_id_missing(monkeypatch):
    telegram = _reload_telegram(monkeypatch, TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="")
    job = _make_job()
    run = _make_run(status=RunStatus.failed, error_text="boom")

    mock_post = AsyncMock()
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.app.services.telegram.httpx.AsyncClient", return_value=mock_client):
        await telegram.notify_run_finished(job=job, run=run, reason="schedule")

    mock_post.assert_not_awaited()


@pytest.mark.asyncio
async def test_success_not_sent_when_disabled(monkeypatch):
    telegram = _reload_telegram(monkeypatch, TELEGRAM_NOTIFY_ON_SUCCESS="false")
    job = _make_job()
    run = _make_run(status=RunStatus.success, size_bytes=100, output_path="/data/out.tar.gz")

    mock_post = AsyncMock()
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.app.services.telegram.httpx.AsyncClient", return_value=mock_client):
        await telegram.notify_run_finished(job=job, run=run, reason="manual")

    mock_post.assert_not_awaited()


@pytest.mark.asyncio
async def test_success_sent_when_enabled(monkeypatch):
    telegram = _reload_telegram(monkeypatch, TELEGRAM_NOTIFY_ON_SUCCESS="true")
    job = _make_job()
    run = _make_run(status=RunStatus.success, size_bytes=2048, output_path="/data/out.tar.gz")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_post = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.app.services.telegram.httpx.AsyncClient", return_value=mock_client):
        await telegram.notify_run_finished(job=job, run=run, reason="schedule")

    mock_post.assert_awaited_once()
    assert "✅ Backup success" in mock_post.await_args.kwargs["json"]["text"]


@pytest.mark.asyncio
async def test_failure_sent_when_enabled(monkeypatch):
    telegram = _reload_telegram(monkeypatch, TELEGRAM_NOTIFY_ON_FAILURE="true")
    job = _make_job()
    run = _make_run(status=RunStatus.failed, error_text="connection refused")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_post = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.app.services.telegram.httpx.AsyncClient", return_value=mock_client):
        await telegram.notify_run_finished(job=job, run=run, reason="manual")

    mock_post.assert_awaited_once()
    assert "connection refused" in mock_post.await_args.kwargs["json"]["text"]


def test_format_message_truncates_long_error(monkeypatch):
    telegram = _reload_telegram(monkeypatch)
    job = _make_job()
    run = _make_run(status=RunStatus.failed, error_text="x" * 5000)

    text = telegram._format_message(job=job, run=run, reason="manual")

    assert len(text) == 4096
    assert text.endswith("...")


@pytest.mark.asyncio
async def test_http_error_does_not_raise(monkeypatch):
    telegram = _reload_telegram(monkeypatch)
    job = _make_job()
    run = _make_run(status=RunStatus.failed, error_text="err")

    mock_post = AsyncMock(side_effect=httpx.HTTPError("network"))
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.app.services.telegram.httpx.AsyncClient", return_value=mock_client):
        await telegram.notify_run_finished(job=job, run=run, reason="manual")
