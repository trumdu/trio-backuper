import errno
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.app.backups import disk
from backend.app.backups.compress import to_targz
from backend.app.backups.utils import dir_size_bytes


def _compress_raw_like_runner(raw_path: Path, archive: Path, *, context: str) -> None:
    raw_size = dir_size_bytes(raw_path)
    if raw_size == 0:
        raise RuntimeError(f"Raw backup empty: {raw_path}")
    disk.ensure_disk_space(archive.parent, raw_size, context=context)
    to_targz(raw_path, archive)


def test_required_temp_bytes() -> None:
    assert disk.required_temp_bytes(100) == 200
    assert disk.required_temp_bytes(0) == 0
    assert disk.required_temp_bytes(1024, multiplier=3) == 3072


def test_format_bytes() -> None:
    assert disk.format_bytes(512) == "512 B"
    assert disk.format_bytes(2048) == "2.00 KiB"
    assert disk.format_bytes(1024 * 1024) == "1.00 MiB"


def _usage(total: int, used: int, free: int) -> SimpleNamespace:
    return SimpleNamespace(total=total, used=used, free=free)


def test_ensure_disk_space_ok(tmp_path: Path) -> None:
    with patch.object(shutil, "disk_usage", return_value=_usage(1000, 100, 500)):
        disk.ensure_disk_space(tmp_path, 100, context="test")


def test_ensure_disk_space_insufficient(tmp_path: Path) -> None:
    with patch.object(shutil, "disk_usage", return_value=_usage(1000, 900, 100)):
        with patch.object(disk.log, "error") as mock_error:
            with pytest.raises(RuntimeError, match="Insufficient disk space for compression \\(test\\)"):
                disk.ensure_disk_space(tmp_path, 100, context="test")
            mock_error.assert_called_once()
            assert mock_error.call_args.args[0] == "disk_space_insufficient"


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (OSError(errno.ENOSPC, "No space left on device"), True),
        (OSError(112, "There is not enough space on the disk"), True),
        (OSError(errno.EACCES, "Permission denied"), False),
        (RuntimeError("Insufficient disk space for compression (postgres): need 1.00 GiB"), True),
        (RuntimeError("pg_dump failed"), False),
        (ValueError("bad"), False),
    ],
)
def test_is_no_space_error(exc: BaseException, expected: bool) -> None:
    assert disk.is_no_space_error(exc) is expected


def test_is_no_space_error_from_cause() -> None:
    inner = OSError(errno.ENOSPC, "No space left on device")
    outer = RuntimeError("wrapped")
    outer.__cause__ = inner
    assert disk.is_no_space_error(outer) is True


def test_compress_raw_empty(tmp_path: Path) -> None:
    raw = tmp_path / "empty.dump"
    raw.touch()
    archive = tmp_path / "backup.tar.gz"

    with pytest.raises(RuntimeError, match="Raw backup empty"):
        _compress_raw_like_runner(raw, archive, context="postgres")


def test_compress_raw_ok(tmp_path: Path) -> None:
    raw = tmp_path / "data.txt"
    raw.write_text("hello backup", encoding="utf-8")
    archive = tmp_path / "backup.tar.gz"

    with patch.object(shutil, "disk_usage", return_value=_usage(10_000, 100, 5000)):
        _compress_raw_like_runner(raw, archive, context="postgres")

    assert archive.is_file()
    assert archive.stat().st_size > 0
