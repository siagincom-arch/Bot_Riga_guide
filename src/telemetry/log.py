"""
Structured JSON logger — JSONL вывод в файл и stderr.

Формат записи: TECH_SPEC §3.4 (request_log).
Конфигурация: LOG_PATH и LOG_LEVEL из src.config.

Хук `scrub_secrets` подготовлен как placeholder для Claude (M2.3).
После реализации scrubber'а он будет фильтровать ключи с TOKEN/API_KEY/SECRET.

Использование:
    from src.telemetry.log import get_logger
    log = get_logger("bot.gateway")
    log.info("request_received", input_type="photo", chat_id=12345)
"""

from __future__ import annotations

import datetime as dt
import logging
import sys
from pathlib import Path
from typing import Any

import structlog


_SECRET_SUBSTRINGS = (
    "TOKEN",
    "API_KEY",
    "SECRET",
    "PASSWORD",
    "AUTH",
    "BEARER",
    "PRIVATE_KEY",
)
_MASK = "***"


def _key_is_secret(key: str) -> bool:
    upper_key = key.upper()
    return any(s in upper_key for s in _SECRET_SUBSTRINGS)


def _mask_value(value: Any) -> Any:
    """Рекурсивно идём внутрь контейнеров, сохраняя структуру."""
    if isinstance(value, dict):
        return {k: (_MASK if _key_is_secret(k) else _mask_value(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_mask_value(v) for v in value)
    # pydantic SecretStr: str(secret) → "**********"; приводим к единому виду
    if value.__class__.__name__ in {"SecretStr", "SecretBytes"}:
        return _MASK
    return value


def scrub_secrets(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """
    Processor для structlog: рекурсивно маскирует секреты в event_dict.

    Правила:
    - Ключ, чьё имя содержит TOKEN/API_KEY/SECRET/PASSWORD/AUTH/BEARER/PRIVATE_KEY
      (регистронезависимо) → значение заменяется на "***".
    - Обход рекурсивен: работает внутри вложенных dict / list / tuple.
    - Значения типа pydantic.SecretStr / SecretBytes → "***" независимо от ключа.
    """
    for key in list(event_dict.keys()):
        if _key_is_secret(key):
            event_dict[key] = _MASK
        else:
            event_dict[key] = _mask_value(event_dict[key])
    return event_dict


def _add_timestamp(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Добавляет ISO-формат timestamp в каждую запись."""
    event_dict["ts"] = dt.datetime.now(dt.timezone.utc).isoformat()
    return event_dict


def setup_logging(log_path: str | Path = "./logs/bot.jsonl", log_level: str = "INFO") -> None:
    """
    Инициализирует structlog + stdlib logging для JSONL-вывода.

    Вызывается один раз при старте приложения.

    Args:
        log_path: путь к файлу JSONL-логов.
        log_level: уровень логирования (DEBUG/INFO/WARNING/ERROR/CRITICAL).
    """
    log_path = Path(log_path)

    # Создаём директорию для логов, если её нет
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Определяем числовой уровень логирования
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # --- stdlib logging: файл + stderr ---
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Удаляем старые хендлеры (безопасно при повторном вызове)
    root_logger.handlers.clear()

    # Хендлер 1: JSONL-файл (основной, append-mode)
    file_handler = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")
    file_handler.setLevel(numeric_level)
    root_logger.addHandler(file_handler)

    # Хендлер 2: stderr (для docker logs)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(numeric_level)
    root_logger.addHandler(stderr_handler)

    # --- structlog конфигурация ---
    structlog.configure(
        processors=[
            # Фильтрация по уровню
            structlog.stdlib.filter_by_level,
            # Добавляем имя логгера
            structlog.stdlib.add_logger_name,
            # Добавляем уровень
            structlog.stdlib.add_log_level,
            # Timestamp в ISO формате
            _add_timestamp,
            # Маскировка секретов (M2.3 — Claude)
            scrub_secrets,
            # Stacktrace при исключениях
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # Декодируем unicode
            structlog.processors.UnicodeDecoder(),
            # Финальный рендер: JSON по одной строке
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        # Привязка к stdlib logging
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Возвращает bound-логгер с заданным именем.

    Args:
        name: имя модуля/компонента, например "bot.gateway" или "rag.graph".

    Returns:
        structlog BoundLogger, пишущий JSON-строки в лог-файл и stderr.
    """
    return structlog.get_logger(name)


def log_request(
    logger: structlog.stdlib.BoundLogger,
    *,
    chat_id: int,
    input_type: str,
    landmark_id: str | None = None,
    latency_ms: int = 0,
    status: str = "ok",
    recognized_confidence: float | None = None,
) -> None:
    """
    Логирует один запрос в формате request_log (TECH_SPEC §3.4).

    Это convenience-обёртка для единообразной записи.
    """
    logger.info(
        "request_log",
        chat_id=chat_id,
        input_type=input_type,
        landmark_id=landmark_id,
        latency_ms=latency_ms,
        status=status,
        recognized_confidence=recognized_confidence,
    )
