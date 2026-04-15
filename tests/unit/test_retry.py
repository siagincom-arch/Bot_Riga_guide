"""
Юнит-тесты для src/llm/retry.py — retry_async политика.

M4.3 — Claude task.
"""

from __future__ import annotations

import pytest

from src.llm.retry import retry_async, with_generate_retry, with_vision_retry


class TestRetryAsync:
    """retry_async: повторы при исключении, возврат результата при успехе."""

    async def test_success_on_first_attempt(self) -> None:
        """Если fn не падает — вызывается один раз, возвращает результат."""
        calls = 0

        async def ok() -> str:
            nonlocal calls
            calls += 1
            return "ok"

        result = await retry_async(ok, attempts=3, backoff_seconds=0.0)
        assert result == "ok"
        assert calls == 1

    async def test_success_on_second_attempt(self) -> None:
        """Падение на первой попытке → успех на второй → возвращается результат."""
        calls = 0

        async def flaky() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("boom")
            return "ok"

        result = await retry_async(flaky, attempts=2, backoff_seconds=0.0)
        assert result == "ok"
        assert calls == 2

    async def test_exhaust_all_attempts_raises(self) -> None:
        """Если все попытки падают — поднимается последнее исключение."""
        calls = 0

        async def always_fails() -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError(f"attempt {calls}")

        with pytest.raises(RuntimeError, match="attempt 3"):
            await retry_async(always_fails, attempts=3, backoff_seconds=0.0)
        assert calls == 3

    async def test_backoff_is_exponential(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Задержка удваивается на каждой попытке."""
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr("asyncio.sleep", fake_sleep)

        async def always_fails() -> str:
            raise RuntimeError("nope")

        with pytest.raises(RuntimeError):
            await retry_async(always_fails, attempts=3, backoff_seconds=0.5)

        # После 1-й попытки: 0.5; после 2-й: 1.0; после 3-й не спим (последняя)
        assert sleeps == [0.5, 1.0]


class TestPolicies:
    """Именованные политики по ARCHITECTURE §6."""

    async def test_vision_retry_retries_once(self) -> None:
        """Vision: 2 попытки (1 retry)."""
        calls = 0

        async def flaky() -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise RuntimeError("transient")
            return "vision_ok"

        result = await with_vision_retry(flaky)
        assert result == "vision_ok"
        assert calls == 2

    async def test_generate_no_retry(self) -> None:
        """Generate: без auto-retry, исключение пробрасывается сразу."""
        calls = 0

        async def fails() -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError("cost control")

        with pytest.raises(RuntimeError):
            await with_generate_retry(fails)
        assert calls == 1
