"""
Юнит-тесты для src/telemetry/log.py — structlog JSONL логирование + scrubber.

M2.4 — AG task.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.telemetry.log import (
    _add_timestamp,
    get_logger,
    log_request,
    scrub_secrets,
    setup_logging,
)


# --- scrub_secrets ---

class TestScrubSecrets:
    """Processor scrub_secrets маскирует значения ключей с секретами."""

    def test_masks_token_key(self) -> None:
        """Ключ содержащий TOKEN → значение заменяется на ***."""
        event: dict[str, Any] = {
            "event": "startup",
            "TELEGRAM_BOT_TOKEN": "real-secret-123",
        }
        result = scrub_secrets(None, "", event)
        assert result["TELEGRAM_BOT_TOKEN"] == "***"

    def test_masks_api_key(self) -> None:
        """Ключ содержащий API_KEY → значение заменяется на ***."""
        event: dict[str, Any] = {
            "event": "init",
            "GEMINI_API_KEY": "AIza-something",
        }
        result = scrub_secrets(None, "", event)
        assert result["GEMINI_API_KEY"] == "***"

    def test_masks_secret_key(self) -> None:
        """Ключ содержащий SECRET → значение заменяется на ***."""
        event: dict[str, Any] = {"db_secret": "password123"}
        result = scrub_secrets(None, "", event)
        assert result["db_secret"] == "***"

    def test_preserves_non_secret_keys(self) -> None:
        """Обычные ключи не трогаем."""
        event: dict[str, Any] = {
            "event": "request_log",
            "chat_id": 12345,
            "input_type": "photo",
            "latency_ms": 350,
        }
        result = scrub_secrets(None, "", event)
        assert result["chat_id"] == 12345
        assert result["input_type"] == "photo"
        assert result["latency_ms"] == 350

    def test_case_insensitive(self) -> None:
        """Поиск подстрок в ключах регистронезависим."""
        event: dict[str, Any] = {
            "my_api_key": "secret-value",
            "some_token": "another-secret",
        }
        result = scrub_secrets(None, "", event)
        assert result["my_api_key"] == "***"
        assert result["some_token"] == "***"

    def test_empty_dict(self) -> None:
        """Пустой event_dict не ломает scrubber."""
        result = scrub_secrets(None, "", {})
        assert result == {}

    def test_password_key_masked(self) -> None:
        """Ключ содержащий PASSWORD → маскируется."""
        event: dict[str, Any] = {"db_password": "p@ss123"}
        result = scrub_secrets(None, "", event)
        assert result["db_password"] == "***"

    def test_nested_dict_scrubbed(self) -> None:
        """Секрет во вложенном словаре тоже маскируется (M2.3)."""
        event: dict[str, Any] = {
            "event": "settings_loaded",
            "settings": {"TELEGRAM_BOT_TOKEN": "xxx", "log_level": "INFO"},
        }
        result = scrub_secrets(None, "", event)
        assert result["settings"]["TELEGRAM_BOT_TOKEN"] == "***"
        assert result["settings"]["log_level"] == "INFO"

    def test_list_of_dicts_scrubbed(self) -> None:
        """Секрет в словаре внутри списка тоже маскируется (M2.3)."""
        event: dict[str, Any] = {
            "event": "batch_requests",
            "calls": [{"url": "/ping"}, {"api_key": "secret-xyz"}],
        }
        result = scrub_secrets(None, "", event)
        assert result["calls"][0]["url"] == "/ping"
        assert result["calls"][1]["api_key"] == "***"

    def test_pydantic_secret_str_masked(self) -> None:
        """Значение с class-name SecretStr маскируется независимо от имени ключа (M2.3).

        Используем локальный stub, чтобы тест не зависел от импорта pydantic.
        Scrubber проверяет тип по имени класса.
        """
        class SecretStr:
            def __init__(self, value: str) -> None:
                self._value = value

        event: dict[str, Any] = {
            "event": "boot",
            "innocent_looking_field": SecretStr("hidden-value"),
        }
        result = scrub_secrets(None, "", event)
        assert result["innocent_looking_field"] == "***"

    def test_auth_and_bearer_keys_masked(self) -> None:
        """AUTH и BEARER — типичные префиксы для токенов — тоже маскируются (M2.3)."""
        event: dict[str, Any] = {
            "Authorization": "Bearer eyJhbGci...",
            "x_bearer_header": "tok_123",
        }
        result = scrub_secrets(None, "", event)
        assert result["Authorization"] == "***"
        assert result["x_bearer_header"] == "***"


# --- _add_timestamp ---

class TestAddTimestamp:
    """Processor _add_timestamp добавляет ISO timestamp."""

    def test_adds_ts_field(self) -> None:
        """В event_dict появляется поле ts."""
        event: dict[str, Any] = {"event": "test"}
        result = _add_timestamp(None, "", event)
        assert "ts" in result
        assert isinstance(result["ts"], str)
        # ISO формат: YYYY-MM-DDTHH:MM:SS...
        assert "T" in result["ts"]

    def test_ts_is_utc(self) -> None:
        """Timestamp содержит метку UTC (+00:00)."""
        event: dict[str, Any] = {"event": "test"}
        result = _add_timestamp(None, "", event)
        assert "+00:00" in result["ts"]


# --- setup_logging ---

class TestSetupLogging:
    """setup_logging создаёт файл и настраивает structlog."""

    def test_creates_log_directory(self, tmp_path: Path) -> None:
        """Если директория для логов не существует — создаётся."""
        log_file = tmp_path / "subdir" / "test.jsonl"
        setup_logging(log_path=log_file, log_level="DEBUG")
        assert log_file.parent.exists()

    def test_logger_writes_json(self, tmp_path: Path) -> None:
        """Логгер пишет валидный JSON в файл."""
        log_file = tmp_path / "test.jsonl"
        setup_logging(log_path=log_file, log_level="DEBUG")

        logger = get_logger("test")
        logger.info("test_event", key="value")

        # Читаем файл и проверяем JSON
        content = log_file.read_text(encoding="utf-8").strip()
        assert content, "Лог-файл не должен быть пустым"

        # Каждая строка — валидный JSON
        for line in content.splitlines():
            parsed = json.loads(line)
            assert "event" in parsed
            assert parsed["event"] == "test_event"
            assert parsed["key"] == "value"

    def test_jsonl_one_line_per_record(self, tmp_path: Path) -> None:
        """Каждая запись — ровно одна строка (JSONL формат)."""
        log_file = tmp_path / "test.jsonl"
        setup_logging(log_path=log_file, log_level="DEBUG")

        logger = get_logger("test_multi")
        logger.info("event_1", n=1)
        logger.info("event_2", n=2)
        logger.info("event_3", n=3)

        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3

        for i, line in enumerate(lines, start=1):
            parsed = json.loads(line)
            assert parsed["n"] == i


# --- log_request ---

class TestLogRequest:
    """Convenience-обёртка log_request пишет поля из TECH_SPEC §3.4."""

    def test_logs_all_fields(self, tmp_path: Path) -> None:
        """log_request записывает все поля request_log."""
        log_file = tmp_path / "req.jsonl"
        setup_logging(log_path=log_file, log_level="DEBUG")

        logger = get_logger("test_request")
        log_request(
            logger,
            chat_id=42,
            input_type="photo",
            landmark_id="dome-cathedral-riga",
            latency_ms=1500,
            status="ok",
            recognized_confidence=0.87,
        )

        content = log_file.read_text(encoding="utf-8").strip()
        parsed = json.loads(content.splitlines()[-1])

        assert parsed["chat_id"] == 42
        assert parsed["input_type"] == "photo"
        assert parsed["landmark_id"] == "dome-cathedral-riga"
        assert parsed["latency_ms"] == 1500
        assert parsed["status"] == "ok"
        assert parsed["recognized_confidence"] == 0.87
        assert "ts" in parsed

    def test_optional_fields_default_to_none(self, tmp_path: Path) -> None:
        """Необязательные поля — null в JSON."""
        log_file = tmp_path / "req2.jsonl"
        setup_logging(log_path=log_file, log_level="DEBUG")

        logger = get_logger("test_optional")
        log_request(
            logger,
            chat_id=99,
            input_type="text",
        )

        content = log_file.read_text(encoding="utf-8").strip()
        parsed = json.loads(content.splitlines()[-1])

        assert parsed["landmark_id"] is None
        assert parsed["latency_ms"] == 0
        assert parsed["status"] == "ok"
        assert parsed["recognized_confidence"] is None
