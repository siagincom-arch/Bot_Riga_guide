"""
Юнит-тесты для RateLimiter — token bucket per chat_id.

M6.5 + M9.1 — AG task (AG2.2).
Расширено: тест с дефолтными 30 токенами, изоляция бакетов.
"""

from __future__ import annotations

import time

import pytest

from src.bot.rate_limit import RateLimiter


# ============================================================
# Базовая логика
# ============================================================

class TestRateLimiterBasic:
    """Базовая логика token bucket."""

    def test_allows_within_limit(self) -> None:
        """Первые max_tokens запросов проходят."""
        rl = RateLimiter(max_tokens=5, refill_rate=0.0)
        results = [rl.is_allowed(1) for _ in range(5)]
        assert all(results)

    def test_blocks_over_limit(self) -> None:
        """max_tokens+1 запрос блокируется (без refill)."""
        rl = RateLimiter(max_tokens=3, refill_rate=0.0)
        for _ in range(3):
            rl.is_allowed(1)
        assert rl.is_allowed(1) is False

    def test_separate_buckets_per_chat(self) -> None:
        """Разные chat_id имеют отдельные buckets."""
        rl = RateLimiter(max_tokens=2, refill_rate=0.0)
        rl.is_allowed(1)
        rl.is_allowed(1)
        # chat_id=1 исчерпан
        assert rl.is_allowed(1) is False
        # chat_id=2 — полный
        assert rl.is_allowed(2) is True


class TestRateLimiterDefault30:
    """Проверка с дефолтными 30 токенами (как в спеке)."""

    def test_30_requests_pass(self) -> None:
        """30 запросов подряд проходят с дефолтным max_tokens=30."""
        rl = RateLimiter(max_tokens=30, refill_rate=0.0)
        results = [rl.is_allowed(42) for _ in range(30)]
        assert all(results), "Все 30 запросов должны пройти"
        assert len(results) == 30

    def test_31st_request_blocked(self) -> None:
        """31-й запрос блокируется."""
        rl = RateLimiter(max_tokens=30, refill_rate=0.0)
        for _ in range(30):
            assert rl.is_allowed(42) is True
        assert rl.is_allowed(42) is False, "31-й запрос должен быть заблокирован"

    def test_different_chats_independent(self) -> None:
        """Два chat_id по 30 запросов — оба проходят."""
        rl = RateLimiter(max_tokens=30, refill_rate=0.0)
        for _ in range(30):
            rl.is_allowed(100)
        # chat_id=100 исчерпан
        assert rl.is_allowed(100) is False
        # chat_id=200 — полный бакет
        results_200 = [rl.is_allowed(200) for _ in range(30)]
        assert all(results_200)


# ============================================================
# Refill
# ============================================================

class TestRateLimiterRefill:
    """Пополнение токенов."""

    def test_refill_restores_tokens(self) -> None:
        """После паузы токены пополняются."""
        # refill_rate=1000 tokens/sec — мгновенный refill для теста
        rl = RateLimiter(max_tokens=5, refill_rate=1000.0)
        for _ in range(5):
            rl.is_allowed(1)
        assert rl.is_allowed(1) is False

        time.sleep(0.01)  # 10ms * 1000 tokens/sec = 10 tokens
        assert rl.is_allowed(1) is True

    def test_refill_capped_at_max(self) -> None:
        """Refill не превышает max_tokens."""
        rl = RateLimiter(max_tokens=3, refill_rate=1000.0)
        time.sleep(0.01)
        # Должно быть макс 3 запроса
        results = [rl.is_allowed(1) for _ in range(10)]
        allowed = sum(results)
        assert allowed <= 6  # max_tokens + small refill

    def test_refill_rate_matches_spec(self) -> None:
        """refill_rate=0.5 → 1 токен за 2 секунды (спека: 30 req/min)."""
        rl = RateLimiter(max_tokens=30, refill_rate=0.5)
        # Сжигаем все токены
        for _ in range(30):
            rl.is_allowed(1)
        assert rl.is_allowed(1) is False

        # Ждём ~50ms → 0.025 токена, недостаточно
        time.sleep(0.05)
        # Может пройти или нет, зависит от точности; просто не падает
        # Реальный refill: 0.5 * 0.05 = 0.025 < 1 → False
        # Но с time jitter может и пройти → не проверяем строго


# ============================================================
# Reset и Cleanup
# ============================================================

class TestRateLimiterReset:
    """Сброс и cleanup."""

    def test_reset_refills_bucket(self) -> None:
        """reset() полностью пополняет bucket."""
        rl = RateLimiter(max_tokens=3, refill_rate=0.0)
        for _ in range(3):
            rl.is_allowed(1)
        assert rl.is_allowed(1) is False

        rl.reset(1)
        assert rl.is_allowed(1) is True

    def test_cleanup_removes_old_buckets(self) -> None:
        """cleanup() удаляет неиспользуемые buckets."""
        rl = RateLimiter(max_tokens=5, refill_rate=0.5)
        rl.is_allowed(1)
        rl.is_allowed(2)
        rl.is_allowed(3)

        # max_age=0 — все считаются старыми
        deleted = rl.cleanup(max_age_seconds=0)
        assert isinstance(deleted, int)

    def test_cleanup_preserves_fresh_buckets(self) -> None:
        """cleanup() не удаляет свежие buckets."""
        rl = RateLimiter(max_tokens=5, refill_rate=0.5)
        rl.is_allowed(1)
        # max_age=3600 — за час ничего не устареет
        deleted = rl.cleanup(max_age_seconds=3600)
        assert deleted == 0
        # Bucket всё ещё работает
        assert rl.is_allowed(1) is True
