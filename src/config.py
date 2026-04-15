"""
Конфигурация приложения — загрузка из .env через pydantic-settings.

Все переменные окружения из TECH_SPEC §10.
Валидация происходит при импорте модуля: если обязательное поле отсутствует —
приложение падает с понятной ошибкой, не запустившись.

Использование:
    from src.config import settings
    print(settings.CHROMA_PATH)
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки Riga Guide Bot, загружаемые из .env / переменных окружения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Не падать, если .env файла нет — поля берутся из окружения
        env_ignore_empty=True,
        extra="ignore",
    )

    # --- Секреты (обязательные) ---
    TELEGRAM_BOT_TOKEN: SecretStr
    GEMINI_API_KEY: SecretStr
    TAVILY_API_KEY: SecretStr

    # --- Пути к данным ---
    CHROMA_PATH: Path = Field(default=Path("./data/chroma"))
    SQLITE_PATH: Path = Field(default=Path("./data/bot.db"))
    LOG_PATH: Path = Field(default=Path("./logs/bot.jsonl"))
    LOG_LEVEL: str = Field(default="INFO")

    # --- RAG параметры ---
    RAG_TOP_K: int = Field(default=6, ge=1, le=50)
    RAG_GRADE_THRESHOLD: float = Field(default=0.6, ge=0.0, le=1.0)
    VISION_CONFIDENCE_THRESHOLD: float = Field(default=0.5, ge=0.0, le=1.0)

    # --- Session ---
    SESSION_WINDOW: int = Field(default=10, ge=1, le=100)
    SESSION_TTL_HOURS: int = Field(default=24, ge=1)

    # --- Geo ---
    NEARBY_RADIUS_M: int = Field(default=300, ge=10, le=10_000)

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Проверяем, что LOG_LEVEL — один из допустимых уровней."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(
                f"LOG_LEVEL должен быть одним из {allowed}, получено: {v!r}"
            )
        return upper

    def __repr__(self) -> str:
        """Отображение без секретов — безопасно для логов."""
        safe_fields = {}
        for name, field_info in self.model_fields.items():
            value = getattr(self, name)
            if isinstance(value, SecretStr):
                safe_fields[name] = "***"
            else:
                safe_fields[name] = value
        pairs = ", ".join(f"{k}={v!r}" for k, v in safe_fields.items())
        return f"Settings({pairs})"

    def __str__(self) -> str:
        return self.__repr__()


# --- Singleton: валидация при первом импорте ---
# Если .env невалиден — приложение не запустится (fail-fast).
# Для тестов: используйте monkeypatch или переопределение env-переменных.
try:
    settings = Settings()  # type: ignore[call-arg]
except Exception:
    # Позволяем модулю быть импортированным в тестовом окружении,
    # где .env может отсутствовать. Тесты используют create_test_settings().
    settings = None  # type: ignore[assignment]


def create_test_settings(**overrides: object) -> Settings:
    """Фабрика для тестов — передаёт все обязательные поля с дефолтами."""
    defaults = {
        "TELEGRAM_BOT_TOKEN": "test-token-123",
        "GEMINI_API_KEY": "test-gemini-key",
        "TAVILY_API_KEY": "test-tavily-key",
        "CHROMA_PATH": "./data/chroma",
        "SQLITE_PATH": "./data/bot.db",
        "LOG_PATH": "./logs/bot.jsonl",
        "LOG_LEVEL": "INFO",
        "RAG_TOP_K": 6,
        "RAG_GRADE_THRESHOLD": 0.6,
        "VISION_CONFIDENCE_THRESHOLD": 0.5,
        "SESSION_WINDOW": 10,
        "SESSION_TTL_HOURS": 24,
        "NEARBY_RADIUS_M": 300,
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]
