from __future__ import annotations

import tarfile
from pathlib import Path


def to_targz(src_path: Path, dest_archive: Path) -> Path:
    dest_archive.parent.mkdir(parents=True, exist_ok=True)
    mode = "w:gz"
    with tarfile.open(dest_archive, mode) as tf:
        # Store inside archive as basename to keep it neat
        arcname = src_path.name
        tf.add(src_path, arcname=arcname, recursive=True)
    return dest_archive

