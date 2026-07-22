"""Async concurrency helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Sequence
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


async def map_concurrent(
    items: Sequence[T],
    worker: Callable[[T], Awaitable[R]],
    *,
    limit: int = 5,
    return_exceptions: bool = True,
) -> list[R | BaseException]:
    semaphore = asyncio.Semaphore(limit)

    async def _run(item: T) -> R | BaseException:
        async with semaphore:
            try:
                return await worker(item)
            except Exception as exc:
                if return_exceptions:
                    return exc
                raise

    return list(await asyncio.gather(*[_run(item) for item in items]))


async def run_with_progress(
    items: Iterable[T],
    worker: Callable[[T], Awaitable[R]],
    *,
    limit: int = 5,
    on_item: Callable[[T, R | BaseException], None] | None = None,
) -> list[R | BaseException]:
    sequence = list(items)
    results: list[R | BaseException] = []
    semaphore = asyncio.Semaphore(limit)

    async def _run(item: T) -> None:
        async with semaphore:
            try:
                result: R | BaseException = await worker(item)
            except Exception as exc:
                result = exc
            results.append(result)
            if on_item:
                on_item(item, result)

    await asyncio.gather(*[_run(item) for item in sequence])
    return results
