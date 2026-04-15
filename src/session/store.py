"""
Session Store — CRUD-обёртка над SQLite для хранения сессий.

TECH_SPEC §3.3, §9:
- Per chat_id, rolling window (SESSION_WINDOW), TTL 24ч.
- /start — сброс сессии.
- Auto-evict при чтении: если сессия старше TTL — удаляется.

SQLite-схема создаётся при инициализации (миграция при старте).
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Optional

from src.session.models import Msg, MsgRole, Session


# SQL для создания таблицы
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    chat_id       INTEGER PRIMARY KEY,
    last_place_id TEXT,
    last_coords   TEXT,
    history       TEXT NOT NULL DEFAULT '[]',
    updated_at    TEXT NOT NULL
);
"""


class SessionStore:
    """
    CRUD-обёртка над SQLite для сессий.

    Потокобезопасность: один инстанс на процесс (MVP — single-process).
    """

    def __init__(self, db_path: str | Path, window: int = 10, ttl_hours: int = 24) -> None:
        self._db_path = str(db_path)
        self._window = window
        self._ttl_hours = ttl_hours
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        """Ленивое подключение с миграцией при первом вызове."""
        if self._conn is None:
            # Создаём директорию, если её нет
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(_CREATE_TABLE)
            self._conn.commit()
        return self._conn

    def get(self, chat_id: int) -> Optional[Session]:
        """
        Возвращает сессию по chat_id или None, если не найдена / истекла.

        Auto-evict: если сессия старше TTL — удаляется и возвращается None.
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT chat_id, last_place_id, last_coords, history, updated_at "
            "FROM sessions WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()

        if row is None:
            return None

        session = self._row_to_session(row)

        # Auto-evict по TTL
        if session.is_expired(self._ttl_hours):
            self.delete(chat_id)
            return None

        return session

    def upsert(self, session: Session) -> None:
        """Создаёт или обновляет сессию. Обрезает историю до window."""
        # Обрезка истории
        if len(session.history) > self._window:
            session.history = session.history[-self._window:]

        session.updated_at = dt.datetime.now(dt.timezone.utc)

        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO sessions (chat_id, last_place_id, last_coords, history, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                last_place_id = excluded.last_place_id,
                last_coords = excluded.last_coords,
                history = excluded.history,
                updated_at = excluded.updated_at
            """,
            (
                session.chat_id,
                session.last_place_id,
                json.dumps(session.last_coords) if session.last_coords else None,
                json.dumps(
                    [{"role": m.role.value, "text": m.text, "ts": m.ts.isoformat()} for m in session.history],
                    ensure_ascii=False,
                ),
                session.updated_at.isoformat(),
            ),
        )
        conn.commit()

    def delete(self, chat_id: int) -> None:
        """Удаляет сессию (используется при /start и автоочистке)."""
        conn = self._get_conn()
        conn.execute("DELETE FROM sessions WHERE chat_id = ?", (chat_id,))
        conn.commit()

    def cleanup_expired(self) -> int:
        """
        Удаляет все истёкшие сессии. Возвращает число удалённых.

        Может вызываться периодически или при старте.
        """
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=self._ttl_hours)
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM sessions WHERE updated_at < ?",
            (cutoff.isoformat(),),
        )
        conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        """Закрывает соединение с базой."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @staticmethod
    def _row_to_session(row: tuple) -> Session:
        """Преобразует строку SQLite в Session."""
        chat_id, last_place_id, last_coords_json, history_json, updated_at_str = row

        # Парсим координаты
        last_coords = json.loads(last_coords_json) if last_coords_json else None

        # Парсим историю
        history_raw = json.loads(history_json)
        history = [
            Msg(
                role=MsgRole(m["role"]),
                text=m["text"],
                ts=dt.datetime.fromisoformat(m["ts"]),
            )
            for m in history_raw
        ]

        return Session(
            chat_id=chat_id,
            last_place_id=last_place_id,
            last_coords=last_coords,
            history=history,
            updated_at=dt.datetime.fromisoformat(updated_at_str),
        )
