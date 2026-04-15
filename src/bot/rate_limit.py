"""
Rate-limiter per chat_id — token bucket in-memory.

M6.5 — AG task.
ARCHITECTURE §9: 30 req/min per chat_id, enforced in Gateway before touching LLM.

Простая in-memory реализация, достаточная для single-process MVP.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    """Один token bucket для конкретного chat_id."""
    tokens: float = 30.0
    last_refill: float = field(default_factory=time.monotonic)


class RateLimiter:
    """
    Per-chat_id rate limiter (token bucket).

    Конфигурация:
        max_tokens: максимальное число токенов (= burst limit).
        refill_rate: токенов в секунду.

    Для 30 req/min: max_tokens=30, refill_rate=0.5 (30/60).
    """

    def __init__(self, max_tokens: int = 30, refill_rate: float = 0.5) -> None:
        self._max_tokens = max_tokens
        self._refill_rate = refill_rate
        self._buckets: dict[int, _Bucket] = defaultdict(
            lambda: _Bucket(tokens=max_tokens)
        )

    def is_allowed(self, chat_id: int) -> bool:
        """
        Проверяет, разрешён ли запрос для chat_id.

        Если разрешён — забирает 1 токен и возвращает True.
        Если нет — возвращает False (rate limit hit).
        """
        bucket = self._buckets[chat_id]
        now = time.monotonic()

        # Refill: добавляем токены за прошедшее время
        elapsed = now - bucket.last_refill
        bucket.tokens = min(
            self._max_tokens,
            bucket.tokens + elapsed * self._refill_rate,
        )
        bucket.last_refill = now

        # Проверяем и списываем
        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True

        return False

    def reset(self, chat_id: int) -> None:
        """Сбрасывает bucket для chat_id (полный refill)."""
        self._buckets[chat_id] = _Bucket(tokens=self._max_tokens)

    def cleanup(self, max_age_seconds: int = 3600) -> int:
        """
        Удаляет старые buckets (не использовались > max_age_seconds).

        Возвращает число удалённых.
        """
        now = time.monotonic()
        to_delete = [
            cid for cid, bucket in self._buckets.items()
            if now - bucket.last_refill > max_age_seconds
        ]
        for cid in to_delete:
            del self._buckets[cid]
        return len(to_delete)
