"""
Юнит-тесты для src/config.py — валидация настроек и маскировка секретов.

M2.4 — AG task.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Settings, create_test_settings


# --- Фабрика тестовых настроек ---

class TestCreateTestSettings:
    """create_test_settings() должна создавать валидный Settings."""

    def test_creates_valid_settings(self) -> None:
        s = create_test_settings()
        assert s is not None
        assert isinstance(s, Settings)

    def test_override_fields(self) -> None:
        s = create_test_settings(RAG_TOP_K=12, SESSION_WINDOW=5)
        assert s.RAG_TOP_K == 12
        assert s.SESSION_WINDOW == 5

    def test_override_log_level(self) -> None:
        s = create_test_settings(LOG_LEVEL="DEBUG")
        assert s.LOG_LEVEL == "DEBUG"


# --- Валидация полей ---

class TestSettingsValidation:
    """Проверяем, что pydantic-settings правильно валидирует поля."""

    def test_defaults_are_correct(self) -> None:
        """Дефолтные значения совпадают с TECH_SPEC §10."""
        s = create_test_settings()
        assert s.CHROMA_PATH == Path("./data/chroma")
        assert s.SQLITE_PATH == Path("./data/bot.db")
        assert s.LOG_PATH == Path("./logs/bot.jsonl")
        assert s.LOG_LEVEL == "INFO"
        assert s.RAG_TOP_K == 6
        assert s.RAG_GRADE_THRESHOLD == 0.6
        assert s.VISION_CONFIDENCE_THRESHOLD == 0.5
        assert s.SESSION_WINDOW == 10
        assert s.SESSION_TTL_HOURS == 24
        assert s.NEARBY_RADIUS_M == 300

    def test_log_level_normalized_to_upper(self) -> None:
        """LOG_LEVEL приводится к верхнему регистру."""
        s = create_test_settings(LOG_LEVEL="debug")
        assert s.LOG_LEVEL == "DEBUG"

    def test_invalid_log_level_raises(self) -> None:
        """Невалидный LOG_LEVEL вызывает ошибку валидации."""
        with pytest.raises(Exception):
            create_test_settings(LOG_LEVEL="TRACE")

    def test_rag_top_k_must_be_positive(self) -> None:
        """RAG_TOP_K не может быть ≤ 0."""
        with pytest.raises(Exception):
            create_test_settings(RAG_TOP_K=0)

    def test_rag_top_k_max_bound(self) -> None:
        """RAG_TOP_K не может быть > 50."""
        with pytest.raises(Exception):
            create_test_settings(RAG_TOP_K=100)

    def test_threshold_bounds(self) -> None:
        """Пороги confidence и grade — от 0 до 1."""
        with pytest.raises(Exception):
            create_test_settings(RAG_GRADE_THRESHOLD=1.5)
        with pytest.raises(Exception):
            create_test_settings(VISION_CONFIDENCE_THRESHOLD=-0.1)

    def test_session_ttl_must_be_positive(self) -> None:
        """SESSION_TTL_HOURS не может быть ≤ 0."""
        with pytest.raises(Exception):
            create_test_settings(SESSION_TTL_HOURS=0)

    def test_nearby_radius_bounds(self) -> None:
        """NEARBY_RADIUS_M: минимум 10, максимум 10000."""
        with pytest.raises(Exception):
            create_test_settings(NEARBY_RADIUS_M=5)
        with pytest.raises(Exception):
            create_test_settings(NEARBY_RADIUS_M=20_000)


# --- Маскировка секретов ---

class TestSecretsMasking:
    """Секреты не должны протекать через repr/str."""

    def test_repr_masks_secrets(self) -> None:
        """В repr секреты заменены на ***."""
        s = create_test_settings(
            TELEGRAM_BOT_TOKEN="super-secret-token",
            GEMINI_API_KEY="gemini-key-value",
            TAVILY_API_KEY="tavily-key-value",
        )
        r = repr(s)
        assert "super-secret-token" not in r
        assert "gemini-key-value" not in r
        assert "tavily-key-value" not in r
        assert "***" in r

    def test_str_masks_secrets(self) -> None:
        """В str секреты заменены на ***."""
        s = create_test_settings(TELEGRAM_BOT_TOKEN="leak-me-not")
        assert "leak-me-not" not in str(s)

    def test_secret_accessible_via_get_secret_value(self) -> None:
        """Реальное значение секрета доступно через .get_secret_value()."""
        s = create_test_settings(TELEGRAM_BOT_TOKEN="my-real-token")
        assert s.TELEGRAM_BOT_TOKEN.get_secret_value() == "my-real-token"


# --- Обязательные поля ---

class TestRequiredFields:
    """Без токенов Settings не должен создаваться (если не тестовая фабрика)."""

    def test_missing_telegram_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Без TELEGRAM_BOT_TOKEN Settings не создаётся."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(Exception):
            Settings(
                _env_file=None,
                GEMINI_API_KEY="key",  # type: ignore[arg-type]
                TAVILY_API_KEY="key",  # type: ignore[arg-type]
                OPENAI_API_KEY="key",  # type: ignore[arg-type]
            )

    def test_missing_gemini_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Без GEMINI_API_KEY Settings не создаётся."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(Exception):
            Settings(
                _env_file=None,
                TELEGRAM_BOT_TOKEN="tok",  # type: ignore[arg-type]
                TAVILY_API_KEY="key",  # type: ignore[arg-type]
                OPENAI_API_KEY="key",  # type: ignore[arg-type]
            )

    def test_missing_tavily_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Без TAVILY_API_KEY Settings не создаётся."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(Exception):
            Settings(
                _env_file=None,
                TELEGRAM_BOT_TOKEN="tok",  # type: ignore[arg-type]
                GEMINI_API_KEY="key",  # type: ignore[arg-type]
                OPENAI_API_KEY="key",  # type: ignore[arg-type]
            )
