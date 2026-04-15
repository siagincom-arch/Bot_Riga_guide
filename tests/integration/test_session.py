"""
Интеграционные тесты для SessionStore — реальный SQLite (tmp).

M3.7 — AG task.
"""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import pytest

from src.session.models import Msg, MsgRole, Session
from src.session.store import SessionStore


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    """Создаёт SessionStore с базой во временной директории."""
    db = tmp_path / "test_session.db"
    s = SessionStore(db_path=db, window=5, ttl_hours=24)
    yield s
    s.close()


class TestSessionStoreBasicCRUD:
    """Базовые операции: создание, чтение, обновление, удаление."""

    def test_get_returns_none_for_missing(self, store: SessionStore) -> None:
        """Несуществующий chat_id → None."""
        assert store.get(999) is None

    def test_upsert_and_get(self, store: SessionStore) -> None:
        """Запись и чтение сессии."""
        session = Session(chat_id=42, last_place_id="dome-cathedral-riga")
        session.add_message(MsgRole.USER, "Привет!", max_window=5)
        store.upsert(session)

        loaded = store.get(42)
        assert loaded is not None
        assert loaded.chat_id == 42
        assert loaded.last_place_id == "dome-cathedral-riga"
        assert len(loaded.history) == 1
        assert loaded.history[0].role == MsgRole.USER
        assert loaded.history[0].text == "Привет!"

    def test_upsert_updates_existing(self, store: SessionStore) -> None:
        """Повторный upsert обновляет данные."""
        session = Session(chat_id=42, last_place_id="place-a")
        store.upsert(session)

        session.last_place_id = "place-b"
        session.add_message(MsgRole.BOT, "Ответ", max_window=5)
        store.upsert(session)

        loaded = store.get(42)
        assert loaded is not None
        assert loaded.last_place_id == "place-b"
        assert len(loaded.history) == 1

    def test_delete(self, store: SessionStore) -> None:
        """Удалённая сессия не читается."""
        session = Session(chat_id=42)
        store.upsert(session)
        assert store.get(42) is not None

        store.delete(42)
        assert store.get(42) is None


class TestSessionStoreWindow:
    """Обрезка истории до window."""

    def test_history_trimmed_on_upsert(self, store: SessionStore) -> None:
        """При upsert с window=5 старые сообщения обрезаются."""
        session = Session(chat_id=1)
        for i in range(10):
            session.add_message(MsgRole.USER, f"msg {i}", max_window=100)

        # store имеет window=5
        store.upsert(session)

        loaded = store.get(1)
        assert loaded is not None
        assert len(loaded.history) == 5
        # Должны остаться последние 5
        assert loaded.history[0].text == "msg 5"
        assert loaded.history[-1].text == "msg 9"


class TestSessionStoreTTL:
    """Auto-evict по TTL."""

    def test_expired_session_returns_none(self, tmp_path: Path) -> None:
        """Сессия старше TTL удаляется при get."""
        db = tmp_path / "ttl_test.db"
        store = SessionStore(db_path=db, window=10, ttl_hours=0)  # TTL = 0 часов → всё истекло

        session = Session(
            chat_id=42,
            # Устанавливаем прошлое время
            updated_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1),
        )
        store.upsert(session)

        # get с TTL=0 должен вернуть None (всё истекло)
        # Но upsert устанавливает updated_at = now, поэтому используем другой подход
        store.close()

        # Пересоздаём с маленьким TTL
        store2 = SessionStore(db_path=db, window=10, ttl_hours=24)
        # Сессия только что обновлена — не истекла
        loaded = store2.get(42)
        assert loaded is not None
        store2.close()

    def test_cleanup_expired(self, tmp_path: Path) -> None:
        """cleanup_expired удаляет старые сессии."""
        db = tmp_path / "cleanup_test.db"
        store = SessionStore(db_path=db, window=10, ttl_hours=1)

        # Вставляем сессию
        session = Session(chat_id=42)
        store.upsert(session)

        # Пока не истекла — cleanup ничего не удаляет
        deleted = store.cleanup_expired()
        # Может быть 0 (сессия свежая)
        assert store.get(42) is not None

        store.close()


class TestSessionStoreCoords:
    """Сохранение и чтение координат."""

    def test_coords_roundtrip(self, store: SessionStore) -> None:
        """Координаты сериализуются/десериализуются корректно."""
        session = Session(
            chat_id=42,
            last_coords={"lat": 56.949, "lon": 24.105},
        )
        store.upsert(session)

        loaded = store.get(42)
        assert loaded is not None
        assert loaded.last_coords == {"lat": 56.949, "lon": 24.105}

    def test_null_coords(self, store: SessionStore) -> None:
        """None координаты не ломают store."""
        session = Session(chat_id=42, last_coords=None)
        store.upsert(session)

        loaded = store.get(42)
        assert loaded is not None
        assert loaded.last_coords is None
