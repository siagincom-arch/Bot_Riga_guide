"""
Pydantic-модели для Session Store — Session и Msg.

Поля из TECH_SPEC §3.3.

Session — состояние разговора per chat_id.
Msg — одно сообщение в окне истории (rolling window, max SESSION_WINDOW).
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MsgRole(str, Enum):
    """Роль автора сообщения в истории."""
    USER = "user"
    BOT = "bot"


class Msg(BaseModel):
    """Одно сообщение в истории диалога."""
    role: MsgRole
    text: str
    ts: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))


class Session(BaseModel):
    """
    Сессия разговора для одного chat_id (TECH_SPEC §3.3).

    Retention: auto-evict после 24ч бездействия.
    Window: максимум SESSION_WINDOW сообщений (по умолчанию 10).
    """
    chat_id: int
    last_place_id: Optional[str] = None
    last_coords: Optional[dict[str, float]] = None  # {"lat": ..., "lon": ...}
    history: list[Msg] = Field(default_factory=list)
    updated_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )

    def add_message(self, role: MsgRole, text: str, max_window: int = 10) -> None:
        """
        Добавляет сообщение в историю с обрезкой до max_window.

        Args:
            role: user или bot.
            text: текст сообщения.
            max_window: максимальное число сообщений в истории.
        """
        self.history.append(Msg(role=role, text=text))
        # Обрезка: оставляем только последние max_window сообщений
        if len(self.history) > max_window:
            self.history = self.history[-max_window:]
        self.updated_at = dt.datetime.now(dt.timezone.utc)

    def is_expired(self, ttl_hours: int = 24) -> bool:
        """Проверяет, истекла ли сессия (TTL с момента последнего обновления)."""
        now = dt.datetime.now(dt.timezone.utc)
        delta = now - self.updated_at
        return delta.total_seconds() > ttl_hours * 3600
