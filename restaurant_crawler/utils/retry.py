"""Tenacity retry helpers."""

from __future__ import annotations

from typing import Callable, TypeVar

from tenacity import (
    AsyncRetrying,
    RetryError,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from restaurant_crawler.utils.logging import get_logger

logger = get_logger()
T = TypeVar("T")


class RetryableError(Exception):
    """Errors that should trigger a retry."""


def sync_retry(
    attempts: int = 5,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            try:
                for attempt in Retrying(
                    stop=stop_after_attempt(attempts),
                    wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                    retry=retry_if_exception_type(exceptions),
                    reraise=True,
                ):
                    with attempt:
                        if attempt.retry_state.attempt_number > 1:
                            logger.warning(
                                "Retry {} for {}",
                                attempt.retry_state.attempt_number,
                                func.__name__,
                            )
                        return func(*args, **kwargs)
            except RetryError as exc:
                raise exc.last_attempt.exception() from exc  # type: ignore[misc]
            raise RuntimeError("unreachable")

        return wrapper

    return decorator


async def async_retry_call(
    func: Callable[..., T],
    *args,
    attempts: int = 5,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    **kwargs,
) -> T:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(exceptions),
        reraise=True,
    ):
        with attempt:
            if attempt.retry_state.attempt_number > 1:
                logger.warning(
                    "Async retry {} for {}",
                    attempt.retry_state.attempt_number,
                    getattr(func, "__name__", str(func)),
                )
            result = func(*args, **kwargs)
            if hasattr(result, "__await__"):
                return await result  # type: ignore[misc]
            return result  # type: ignore[return-value]
    raise RuntimeError("unreachable")
