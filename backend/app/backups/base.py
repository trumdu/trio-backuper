from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RawBackup:
    path: Path
    log_text: str


class BackupSource(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def test_connection(self) -> None: ...

    @abstractmethod
    async def backup_raw(self, out_dir: Path) -> RawBackup: ...

    @abstractmethod
    def redact(self) -> dict[str, Any]: ...

