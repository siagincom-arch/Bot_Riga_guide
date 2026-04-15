"""
Retry-политика для LLM-вызовов.

ARCHITECTURE §6: Vision/Generate — 1 retry с backoff, остальное (embed/Tavily) — без retry.
Применение: оборачиваем вызов gemini.generate / gemini.vision в RAG-узлах через `retry_async`.

Не встроено в GeminiClient намеренно: разные узлы имеют разную политику
(hallucination_check делает ручной retry через перегенерацию, а не сетевой retry).
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypeVar

from src.telemetry.log import get_logger

logger = get_logger("llm.retry")

T = TypeVar("T")


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 2,
    backoff_seconds: float = 1.0,
    label: str = "llm_call",
) -> T:
    """
    Выполняет async-корутину с повторами при исключении.

    Политика по умолчанию: 2 попытки (1 оригинал + 1 retry), backoff экспоненциальный
    от `backoff_seconds` — достаточно для короткого сбоя Gemini 5xx.

    Args:
        fn: фабрика корутины — вызывается повторно на каждой попытке.
            Передаём именно фабрику, а не awaitable, потому что awaitable нельзя await'ить дважды.
        attempts: общее количество попыток (включая первую).
        backoff_seconds: базовая задержка; на i-й попытке ждём backoff_seconds * 2**(i-1).
        label: имя для логов (например, "gemini.generate").

    Returns:
        Результат успешного вызова fn().

    Raises:
        Последнее пойманное исключение, если все попытки провалились.
    """
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                logger.warning(
                    "retry.exhausted",
                    label=label,
                    attempts=attempts,
                    error=repr(exc),
                )
                raise
            delay = backoff_seconds * (2 ** (attempt - 1))
            logger.info(
                "retry.attempt_failed",
                label=label,
                attempt=attempt,
                next_delay_s=delay,
                error=repr(exc),
            )
            await asyncio.sleep(delay)

    # Недостижимо, но mypy strict требует явного return/raise
    assert last_exc is not None
    raise last_exc


# Короткие именованные политики по ARCHITECTURE §6
async def with_vision_retry(fn: Callable[[], Awaitable[T]]) -> T:
    """Vision: 1 retry (total 2 attempts), backoff 1s."""
    return await retry_async(fn, attempts=2, backoff_seconds=1.0, label="gemini.vision")


async def with_generate_retry(fn: Callable[[], Awaitable[T]]) -> T:
    """Generate: без auto-retry (cost control). Помечен явно для читаемости call-site."""
    return await fn()
