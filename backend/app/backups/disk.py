from __future__ import annotations

import errno
import logging
import shutil
from pathlib import Path

log = logging.getLogger(__name__)

_TEMP_SPACE_MULTIPLIER = 2


def get_free_bytes(path: Path) -> int:
    return int(shutil.disk_usage(path).free)


def required_temp_bytes(uncompressed_bytes: int, *, multiplier: int = _TEMP_SPACE_MULTIPLIER) -> int:
    return int(uncompressed_bytes) * multiplier


def format_bytes(n: int) -> str:
    value = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024.0 or unit == "TiB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} TiB"


def ensure_disk_space(path: Path, uncompressed_bytes: int, *, context: str) -> None:
    required = required_temp_bytes(uncompressed_bytes)
    free = get_free_bytes(path)
    if free >= required:
        return

    msg = (
        f"Insufficient disk space for compression ({context}): "
        f"need {format_bytes(required)} (uncompressed {format_bytes(uncompressed_bytes)} × {_TEMP_SPACE_MULTIPLIER}), "
        f"free {format_bytes(free)}"
    )
    log.error(
        "disk_space_insufficient",
        extra={
            "context": context,
            "path": str(path),
            "uncompressed_bytes": uncompressed_bytes,
            "required_bytes": required,
            "free_bytes": free,
        },
    )
    raise RuntimeError(msg)


def is_no_space_error(exc: BaseException) -> bool:
    if isinstance(exc, OSError) and exc.errno in (errno.ENOSPC, 112):
        return True
    if isinstance(exc, RuntimeError) and "Insufficient disk space" in str(exc):
        return True
    cause = exc.__cause__
    if cause is not None and cause is not exc:
        return is_no_space_error(cause)
    return False
