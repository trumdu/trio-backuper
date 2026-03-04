from fastapi.testclient import TestClient

from backend.app.main import app


def test_jobs_crud_smoke():
    with TestClient(app) as c:
        r = c.get("/api/jobs")
        assert r.status_code == 200

        payload = {
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
        r = c.post("/api/jobs", json=payload)
        assert r.status_code == 200, r.text
        job = r.json()
        assert job["name"] == "t1"
        assert job["postgres"]["password"] == "********"

        r = c.get(f"/api/jobs/{job['id']}")
        assert r.status_code == 200

        r = c.put(f"/api/jobs/{job['id']}", json={"enabled": False})
        assert r.status_code == 200
        assert r.json()["enabled"] is False

        r = c.delete(f"/api/jobs/{job['id']}")
        assert r.status_code == 200
        assert r.json()["deleted"] is True
