import os

from cryptography.fernet import Fernet


def pytest_configure():
    # Ensure required settings exist before backend imports.
    os.environ.setdefault("APP_ENV", "dev")
    os.environ.setdefault("SECRETS_FERNET_KEY", Fernet.generate_key().decode())
    os.environ.setdefault("DB_PATH", "data/test_app.db")
    os.environ.setdefault("LOG_DIR", "data/test_logs")
    os.environ.setdefault("BACKUP_ROOT", "data/test_backups")
