import tarfile
from pathlib import Path

import pytest

from backend.app.backups.compress import to_targz, verify_targz


def test_verify_targz_ok(tmp_path: Path) -> None:
    src = tmp_path / "data.txt"
    src.write_text("hello backup", encoding="utf-8")
    archive = tmp_path / "backup.tar.gz"
    to_targz(src, archive)

    result = verify_targz(archive)

    assert result.startswith("integrity_ok: backup.tar.gz")
    assert "members=1" in result
    assert "bytes=12" in result


def test_verify_targz_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Archive missing"):
        verify_targz(tmp_path / "missing.tar.gz")


def test_verify_targz_corrupt(tmp_path: Path) -> None:
    archive = tmp_path / "corrupt.tar.gz"
    archive.write_bytes(b"not a valid gzip archive")

    with pytest.raises((OSError, EOFError, tarfile.ReadError, tarfile.TarError)):
        verify_targz(archive)


def test_verify_targz_empty(tmp_path: Path) -> None:
    archive = tmp_path / "empty.tar.gz"
    archive.write_bytes(b"")

    with pytest.raises(ValueError, match="Archive empty"):
        verify_targz(archive)
