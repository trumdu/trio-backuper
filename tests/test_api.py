import importlib
import json
import sys

from fastapi.testclient import TestClient
from cryptography.fernet import Fernet



def _build_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("BACKUP_ROOT", str(tmp_path / "backups"))
    monkeypatch.setenv("SECRETS_FERNET_KEY", Fernet.generate_key().decode("utf-8"))

    cfg_path = tmp_path / "config.json"
    monkeypatch.setenv("CONFIG_PATH", str(cfg_path))

    # Ensure settings / cipher pick up env vars for each test.
    for m in [
        "backend.app.core.config",
        "backend.app.core.security",
        "backend.app.services.secrets_json",
        "backend.app.main",
    ]:
        sys.modules.pop(m, None)

    import backend.app.main as main

    importlib.reload(main)
    return main.app, cfg_path


def test_jobs_synced_from_config(tmp_path, monkeypatch):
    app, cfg_path = _build_app(tmp_path, monkeypatch)

    job1 = {
        "name": "t1",
        "source_type": "postgres",
        "schedule_cron": "0 2 * * *",
        "destination_path": "default",
        "enabled": True,
        "postgres": {
            "host": "localhost",
            "port": 5432,
            "database": "db",
            "user": "u",
            "password": "p",
            "sslmode": "prefer",
            "format": "custom",
        },
    }
    cfg_path.write_text(json.dumps([job1], ensure_ascii=False), encoding="utf-8")

    with TestClient(app) as c:
        # Initial sync happens on startup, but we also expose explicit sync endpoint.
        r = c.post("/api/jobs/sync-from-config", json={})
        assert r.status_code == 200, r.text

        r = c.get("/api/jobs")
        assert r.status_code == 200
        jobs = r.json()
        assert len(jobs) == 1
        assert jobs[0]["name"] == "t1"
        assert jobs[0]["postgres"]["password"] == "********"

        # Add one more job via config and resync.
        job2 = {
            "name": "t2",
            "source_type": "mongo",
            "schedule_cron": "30 2 * * *",
            "destination_path": "default",
            "enabled": True,
            "mongo": {
                "host": "localhost",
                "port": 27017,
                "database": "db",
                "user": "u",
                "password": "p",
                "authSource": "admin",
            },
        }
        cfg_path.write_text(json.dumps([job1, job2], ensure_ascii=False), encoding="utf-8")

        r = c.post("/api/jobs/sync-from-config", json={})
        assert r.status_code == 200, r.text

        r = c.get("/api/jobs")
        assert r.status_code == 200
        names = [j["name"] for j in r.json()]
        assert names == ["t1", "t2"]
