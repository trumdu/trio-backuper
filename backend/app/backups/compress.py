from __future__ import annotations

import tarfile
from pathlib import Path

_READ_CHUNK = 1024 * 1024


def to_targz(src_path: Path, dest_archive: Path) -> Path:
    dest_archive.parent.mkdir(parents=True, exist_ok=True)
    mode = "w:gz"
    with tarfile.open(dest_archive, mode) as tf:
        # Store inside archive as basename to keep it neat
        arcname = src_path.name
        tf.add(src_path, arcname=arcname, recursive=True)
    return dest_archive


def verify_targz(archive: Path) -> str:
    if not archive.is_file():
        raise FileNotFoundError(f"Archive missing: {archive}")
    if archive.stat().st_size == 0:
        raise ValueError(f"Archive empty: {archive}")

    members = 0
    bytes_read = 0
    with tarfile.open(archive, mode="r:gz") as tf:
        for member in tf.getmembers():
            members += 1
            if not member.isfile():
                continue
            f = tf.extractfile(member)
            if f is None:
                continue
            with f:
                while True:
                    chunk = f.read(_READ_CHUNK)
                    if not chunk:
                        break
                    bytes_read += len(chunk)

    if members == 0:
        raise ValueError(f"Archive has no members: {archive}")

    return f"integrity_ok: {archive.name} (members={members}, bytes={bytes_read})"

