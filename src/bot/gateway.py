"""
Bot Gateway — хендлеры Telegram-сообщений.

M6.2 + M6.7 — AG, M6.4 — Claude (i18n), M6.6 + RAG-интеграция — Claude (блоки C–G).
TECH_SPEC §4.1–4.2: команды, обработчики фото/гео/текст, callback queries.
Пользовательские строки — в src/bot/i18n_ru.py.
"""

from __future__ import annotations

import time
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from src.bot import i18n_ru as i18n
from src.bot.photo_utils import download_largest
from src.bot.rate_limit import RateLimiter
from src.bot.ui import (
    format_answer,
    format_interim_ack,
    format_nearby_list,
    make_nearby_keyboard,
    make_place_keyboard,
)
from src.rag.singleton import run_rag
from src.session.models import MsgRole, Session
from src.session.store import SessionStore
from src.telemetry.log import get_logger, log_request

import asyncio
from telegram import Message

class StreamUpdater:
    """Обертка для безопасного обновления сообщения Telegram с учетом rate-limits."""
    def __init__(self, message: Message, update_interval: float = 1.5):
        self.message = message
        self.update_interval = update_interval
        self.last_update_time = time.monotonic()
        self.accumulated_text = ""
        self._is_updating = False

    async def on_chunk(self, chunk: str) -> None:
        if not chunk:
            return
        
        self.accumulated_text += chunk
        now = time.monotonic()
        if now - self.last_update_time >= self.update_interval and not self._is_updating:
            self._is_updating = True
            try:
                # Ограничиваем длину превью, если оно слишком большое
                # Не добавляем клавиатуру, так как это промежуточный статус
                await self.message.edit_text(
                    self.accumulated_text[:4000] + "...",
                    parse_mode=None  # Отключаем HTML для безопасности на сыром пайплайне
                )
                self.last_update_time = time.monotonic()
            except Exception as e:
                # Telegram ругается, если текст не изменился (Message is not modified) – игнорируем
                pass
            finally:
                self._is_updating = False


def _session_history_for_rag(session: Session, limit: int = 4) -> list[dict]:
    """Возвращает последние N сообщений в формате, который ожидает generate.j2."""
    msgs = session.history[-limit:] if session.history else []
    return [{"role": m.role.value, "text": m.text} for m in msgs]


def _compose_answer(result: dict) -> str:
    """Склейка summary+story из результата RAG с опциональным маркером uncertain."""
    summary = result.get("summary") or ""
    story = result.get("story") or ""
    body = format_answer(summary, story)
    return body

logger = get_logger("bot.gateway")

# --- Глобальные объекты (инициализируются при старте бота) ---
# В MVP — singleton'ы, т.к. single-process.
_rate_limiter = RateLimiter(max_tokens=30, refill_rate=0.5)
_session_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """Lazy-init сессионного стора. Вызывается из хендлеров."""
    global _session_store
    if _session_store is None:
        from src.config import settings
        if settings is None:
            raise RuntimeError("Settings not loaded")
        _session_store = SessionStore(
            db_path=settings.SQLITE_PATH,
            window=settings.SESSION_WINDOW,
            ttl_hours=settings.SESSION_TTL_HOURS,
        )
    return _session_store


def _check_rate_limit(chat_id: int) -> bool:
    """Возвращает True, если запрос разрешён."""
    return _rate_limiter.is_allowed(chat_id)


# ============================================================
# Команды
# ============================================================

async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start — приветствие + сброс сессии.

    TECH_SPEC §4.1.
    """
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    start_time = time.monotonic()

    logger.info("cmd.start", chat_id=chat_id)

    # Сброс сессии (TECH_SPEC §9)
    store = get_session_store()
    store.delete(chat_id)

    await update.message.reply_text(i18n.START_GREETING, parse_mode="HTML")  # type: ignore[union-attr]

    latency = int((time.monotonic() - start_time) * 1000)
    log_request(logger, chat_id=chat_id, input_type="command", status="ok", latency_ms=latency)


async def on_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /help — краткая справка.

    TECH_SPEC §4.1.
    """
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    logger.info("cmd.help", chat_id=chat_id)

    await update.message.reply_text(i18n.HELP_TEXT, parse_mode="HTML")  # type: ignore[union-attr]


async def on_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /about — информация о боте.

    TECH_SPEC §4.1.
    """
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    logger.info("cmd.about", chat_id=chat_id)

    await update.message.reply_text(i18n.ABOUT_TEXT, parse_mode="HTML")  # type: ignore[union-attr]


# ============================================================
# Обработчики сообщений
# ============================================================

async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка фото — двухэтапный ответ (ADR-5).

    TECH_SPEC §4.2: on_photo.
    Flow: PHOTO_SEEING → download → run_rag(photo) → (interim ack с place_name?) → полный ответ.
    Два отдельных reply_text (не edit), чтобы триггерить push-уведомления.
    """
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    start_time = time.monotonic()

    logger.info("msg.photo", chat_id=chat_id)

    if not _check_rate_limit(chat_id):
        await update.message.reply_text(i18n.RATE_LIMIT_HIT)  # type: ignore[union-attr]
        return

    # Первое сообщение — «смотрю фото» (сразу, до скачивания).
    reply_msg = await update.message.reply_text(i18n.PHOTO_SEEING, parse_mode="HTML")  # type: ignore[union-attr]
    updater = StreamUpdater(reply_msg)

    # Сессия
    store = get_session_store()
    session = store.get(chat_id) or Session(chat_id=chat_id)

    status = "ok"
    place_id: str | None = None

    # Скачивание фото
    try:
        image_bytes = await download_largest(update.message)  # type: ignore[arg-type]
    except ValueError as e:
        logger.warning("msg.photo.download_error", error=str(e))
        await update.message.reply_text(i18n.PHOTO_DOWNLOAD_ERROR)  # type: ignore[union-attr]
        session.add_message(MsgRole.USER, "[photo: download_error]")
        try:
            store.upsert(session)
        except Exception as se:
            logger.warning("session.update.error", error=str(se))
        latency = int((time.monotonic() - start_time) * 1000)
        log_request(logger, chat_id=chat_id, input_type="photo", status="download_error", latency_ms=latency)
        return

    # RAG
    try:
        result = await run_rag({
            "input_type": "photo",
            "image_bytes": image_bytes,
            "chat_id": chat_id,
            "session_history": _session_history_for_rag(session),
            "stream_callback": updater.on_chunk,
        })
        place_id = result.get("place_id")
        place_name = result.get("place_name")

        if status == "not_recognized":
            await reply_msg.edit_text(
                i18n.PHOTO_NOT_RECOGNIZED, parse_mode="HTML"
            )
            session.add_message(MsgRole.USER, "[photo: not_recognized]")
        elif status in ("llm_error", "timeout"):
            await reply_msg.edit_text(i18n.VISION_ERROR)
            session.add_message(MsgRole.USER, "[photo: llm_error]")
        else:
            answer = _compose_answer(result)
            keyboard = make_place_keyboard(place_id) if place_id else None
            await reply_msg.edit_text(
                answer, parse_mode="HTML", reply_markup=keyboard
            )

            session.add_message(MsgRole.USER, f"[photo: {place_name or 'неизвестно'}]")
            session.add_message(MsgRole.BOT, (result.get("summary") or "")[:500])
            if place_id:
                session.last_place_id = place_id

    except Exception as e:
        logger.error("msg.photo.rag_error", error=str(e))
        status = "llm_error"
        await reply_msg.edit_text(i18n.VISION_ERROR)
        session.add_message(MsgRole.USER, "[photo: llm_error]")

    try:
        store.upsert(session)
    except Exception as e:
        logger.warning("session.update.error", error=str(e))

    latency = int((time.monotonic() - start_time) * 1000)
    log_request(logger, chat_id=chat_id, input_type="photo", status=status, latency_ms=latency)


async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка геолокации — geo_nearby → список мест.

    TECH_SPEC §4.2: on_location.
    """
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    start_time = time.monotonic()
    location = update.message.location  # type: ignore[union-attr]

    logger.info("msg.location", chat_id=chat_id, lat=location.latitude, lon=location.longitude)

    if not _check_rate_limit(chat_id):
        await update.message.reply_text(i18n.RATE_LIMIT_HIT)  # type: ignore[union-attr]
        return

    # TODO (M5 — Claude): полный pipeline через RAG graph
    # Пока — прямой вызов KBStore.geo_nearby

    try:
        from src.config import settings
        from src.kb.store import KBStore

        if settings is None:
            raise RuntimeError("Settings не загружены")

        kb = KBStore(chroma_path=settings.CHROMA_PATH, sqlite_path=settings.SQLITE_PATH)
        places = kb.geo_nearby(
            lat=location.latitude,
            lon=location.longitude,
            radius_m=settings.NEARBY_RADIUS_M,
            limit=3,
        )

        if places:
            text = format_nearby_list(places)
            keyboard = make_nearby_keyboard(places)
            status = "ok"
        else:
            text = i18n.GEO_OUT_OF_COVERAGE
            keyboard = None
            status = "no_kb"

        await update.message.reply_text(  # type: ignore[union-attr]
            text, parse_mode="HTML", reply_markup=keyboard
        )

        # Обновляем сессию (M6.7)
        store = get_session_store()
        session = store.get(chat_id) or Session(chat_id=chat_id)
        session.last_coords = {"lat": location.latitude, "lon": location.longitude}
        session.add_message(MsgRole.USER, f"[geo: {location.latitude}, {location.longitude}]")
        store.upsert(session)
    except Exception as e:
        logger.error("msg.location.error", error=str(e))
        await update.message.reply_text(i18n.GENERIC_ERROR)  # type: ignore[union-attr]
        status = "llm_error"

    latency = int((time.monotonic() - start_time) * 1000)
    log_request(logger, chat_id=chat_id, input_type="geo", status=status, latency_ms=latency)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка текстового запроса — text_search → ответ.

    TECH_SPEC §4.2: on_text.
    """
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    text_query = update.message.text.strip()  # type: ignore[union-attr]
    start_time = time.monotonic()

    logger.info("msg.text", chat_id=chat_id, query=text_query[:100])

    if not _check_rate_limit(chat_id):
        await update.message.reply_text(i18n.RATE_LIMIT_HIT)  # type: ignore[union-attr]
        return

    # Загружаем сессию и добавляем пользовательское сообщение
    store = get_session_store()
    session = store.get(chat_id) or Session(chat_id=chat_id)
    session.add_message(MsgRole.USER, text_query)

    status = "ok"
    place_id: str | None = None

    reply_msg = await update.message.reply_text(
        i18n.TEXT_SEARCHING_TMPL.format(query=text_query), 
        parse_mode="HTML"
    )
    updater = StreamUpdater(reply_msg)

    try:
        result = await run_rag({
            "input_type": "text",
            "query": text_query,
            "chat_id": chat_id,
            "session_history": _session_history_for_rag(session),
            "stream_callback": updater.on_chunk,
        })
        status = result.get("status") or "ok"
        place_id = result.get("place_id")

        if status == "not_recognized" or status == "no_kb":
            await reply_msg.edit_text(
                i18n.TEXT_NOT_FOUND_TMPL.format(query=text_query),
                parse_mode="HTML",
            )
        elif status in ("llm_error", "timeout"):
            await reply_msg.edit_text(i18n.LLM_ERROR)
        else:
            answer = _compose_answer(result)
            keyboard = make_place_keyboard(place_id) if place_id else None
            await reply_msg.edit_text(
                answer, parse_mode="HTML", reply_markup=keyboard
            )
            # Сохраняем ответ в историю (урезанный до разумной длины)
            session.add_message(MsgRole.BOT, (result.get("summary") or "")[:500])
            if place_id:
                session.last_place_id = place_id

    except Exception as e:
        logger.error("msg.text.rag_error", error=str(e))
        status = "llm_error"
        await reply_msg.edit_text(i18n.LLM_ERROR)

    # Сохраняем сессию
    try:
        store.upsert(session)
    except Exception as e:
        logger.warning("session.update.error", error=str(e))

    latency = int((time.monotonic() - start_time) * 1000)
    log_request(logger, chat_id=chat_id, input_type="text", status=status, latency_ms=latency)


async def _run_followup(
    query: Any,
    chat_id: int,
    place_id: str,
    *,
    extra_user_prompt: str | None = None,
) -> None:
    """
    Общая логика для callback'ов `tell:` и `more_legend:` — запуск RAG в режиме followup.

    Args:
        query: CallbackQuery (нужен .message.reply_text).
        chat_id: Telegram chat id.
        place_id: известный идентификатор места (из предыдущего ответа).
        extra_user_prompt: если задан — добавляется в session_history как user-сообщение
            перед вызовом графа (используется для «ещё легенда»).
    """
    store = get_session_store()
    session = store.get(chat_id) or Session(chat_id=chat_id)
    if extra_user_prompt:
        session.add_message(MsgRole.USER, extra_user_prompt)

    # Отправляем сообщение для стриминга (TELL_LOADING_TMPL)
    loading_tmpl = i18n.MORE_LEGEND_LOADING_TMPL if extra_user_prompt else i18n.TELL_LOADING_TMPL
    # Мы не можем отобразить настоящее название без доп. запроса в БД, пока просто покажем заглушку со словом "место" или опустим.
    # Шаблоны требуют {place_name}, но у нас только place_id. Заменим на универсальное "Интересное место".
    reply_msg = await query.message.reply_text(
        loading_tmpl.format(place_name="..."), parse_mode="HTML"
    )
    updater = StreamUpdater(reply_msg)

    status = "ok"
    try:
        result = await run_rag({
            "input_type": "followup",
            "place_id": place_id,
            "chat_id": chat_id,
            "session_history": _session_history_for_rag(session),
            "stream_callback": updater.on_chunk,
        })
        status = result.get("status") or "ok"

        if status in ("llm_error", "timeout"):
            await reply_msg.edit_text(i18n.LLM_ERROR)
        elif status == "no_kb":
            await reply_msg.edit_text(
                i18n.TEXT_NOT_FOUND_TMPL.format(query=place_id), parse_mode="HTML"
            )
        else:
            answer = _compose_answer(result)
            keyboard = make_place_keyboard(place_id)
            await reply_msg.edit_text(
                answer, parse_mode="HTML", reply_markup=keyboard
            )
            session.add_message(MsgRole.BOT, (result.get("summary") or "")[:500])
            session.last_place_id = place_id

    except Exception as e:
        logger.error("callback.followup.rag_error", error=str(e), place_id=place_id)
        status = "llm_error"
        await reply_msg.edit_text(i18n.LLM_ERROR)

    try:
        store.upsert(session)
    except Exception as e:
        logger.warning("session.update.error", error=str(e))

    log_request(logger, chat_id=chat_id, input_type="callback", status=status)


# ============================================================
# Callback queries
# ============================================================

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка callback queries: tell:<place_id>, more_legend:<place_id>, nearby:<place_id>.

    TECH_SPEC §4.2.
    """
    query = update.callback_query
    if query is None:
        return

    await query.answer()  # Убираем «часики» в Telegram

    data = query.data or ""
    chat_id = query.message.chat.id  # type: ignore[union-attr]

    logger.info("callback", chat_id=chat_id, data=data)

    if not _check_rate_limit(chat_id):
        await query.message.reply_text(i18n.RATE_LIMIT_HIT)  # type: ignore[union-attr]
        return

    if data.startswith("tell:"):
        place_id = data.removeprefix("tell:")
        await _run_followup(query, chat_id, place_id, extra_user_prompt=None)

    elif data.startswith("more_legend:"):
        place_id = data.removeprefix("more_legend:")
        await _run_followup(
            query, chat_id, place_id, extra_user_prompt=i18n.MORE_LEGEND_PROMPT
        )

    elif data.startswith("nearby:"):
        place_id = data.removeprefix("nearby:")
        
        from src.config import settings
        from src.kb.store import KBStore

        if settings is None:
            raise RuntimeError("Settings не загружены")

        kb = KBStore(chroma_path=settings.CHROMA_PATH, sqlite_path=settings.SQLITE_PATH)
        coords = kb.get_coords(place_id)
        
        if coords:
            lat, lon = coords
            places = kb.geo_nearby(
                lat=lat,
                lon=lon,
                radius_m=settings.NEARBY_RADIUS_M,
                # берём 4, на случай если мы исключим сам place_id
                limit=4,
            )
            
            # Убираем исходное место
            places = [p for p in places if p["place_id"] != place_id][:3]

            if places:
                text = format_nearby_list(places)
                keyboard = make_nearby_keyboard(places)
                await query.message.reply_text(
                    text, parse_mode="HTML", reply_markup=keyboard
                )
            else:
                await query.message.reply_text(i18n.GEO_OUT_OF_COVERAGE, parse_mode="HTML")
        else:
            await query.message.reply_text(i18n.GENERIC_ERROR, parse_mode="HTML")

    else:
        logger.warning("callback.unknown", data=data)

    log_request(logger, chat_id=chat_id, input_type="callback", status="ok")
