from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay_s: float = 1.0,
    max_delay_s: float = 10.0,
) -> T:
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as e:
            last_exc = e
            if i == attempts - 1:
                break
            delay = min(max_delay_s, base_delay_s * (2**i))
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc

