"""
UI-утилиты для Telegram — клавиатуры и форматирование ответов.

M6.3 — AG task.
TECH_SPEC §4.3: inline buttons [🎭 Ещё легенда] [📍 Что рядом].
Форматирование ответа: summary (bold) + story + buttons.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def make_place_keyboard(place_id: str) -> InlineKeyboardMarkup:
    """
    Клавиатура под основным ответом: «Ещё легенда» и «Что рядом».

    Args:
        place_id: ID места для callback_data.
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎭 Ещё легенда", callback_data=f"more_legend:{place_id}"),
            InlineKeyboardButton("📍 Что рядом", callback_data=f"nearby:{place_id}"),
        ]
    ])


def make_nearby_keyboard(places: list[dict]) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком ближайших мест.

    Args:
        places: список dict с place_id, name_ru, distance_m.
    """
    buttons = []
    for p in places[:3]:
        label = f"📍 {p['name_ru']} ({p['distance_m']:.0f} м)"
        buttons.append([
            InlineKeyboardButton(label, callback_data=f"tell:{p['place_id']}")
        ])
    return InlineKeyboardMarkup(buttons)


def format_answer(summary: str, story: str) -> str:
    """
    Форматирует двухблочный ответ для Telegram (HTML mode).

    Args:
        summary: энциклопедическая справка (2-3 предложения).
        story: живой рассказ (7-8 предложений).

    Returns:
        HTML-форматированный текст для parse_mode="HTML".
    """
    parts = []

    if summary:
        parts.append(f"<b>📖 Справка</b>\n{summary}")

    if story:
        parts.append(f"<b>🏛 История</b>\n{story}")

    return "\n\n".join(parts) if parts else "У меня пока нет информации об этом месте."


def format_interim_ack(place_name: str) -> str:
    """
    Промежуточное сообщение после распознавания фото.

    ARCHITECTURE ADR-5: отправляется как новое сообщение (не edit), чтобы триггерить push.
    """
    return f"📸 Вижу <b>{place_name}</b>! Собираю историю…"


def format_nearby_list(places: list[dict]) -> str:
    """
    Текст для ответа на геолокацию.
    """
    if not places:
        return "😕 Рядом с вами не нашлось известных мне мест. Попробуйте подойти ближе к достопримечательности."

    lines = ["📍 <b>Рядом с вами:</b>"]
    for i, p in enumerate(places[:3], 1):
        lines.append(f"{i}. {p['name_ru']} — {p['distance_m']:.0f} м")
    lines.append("\nНажмите на место, чтобы узнать его историю 👇")
    return "\n".join(lines)


def make_menu_keyboard() -> InlineKeyboardMarkup:
    """6 кнопок меню в раскладке 2×3."""
    from src.bot import i18n_ru as i18n
    rows = []
    buttons = i18n.MENU_BUTTONS
    for i in range(0, len(buttons), 2):
        row = [
            InlineKeyboardButton(text=label, callback_data=cb)
            for label, cb in buttons[i:i+2]
        ]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def make_examples_keyboard() -> InlineKeyboardMarkup:
    """3 кнопки-примера с switch_inline_query_current_chat —
    при тапе подставляют текст в поле ввода (не отправляют)."""
    from src.bot import i18n_ru as i18n
    rows = [
        [InlineKeyboardButton(
            text=example,
            switch_inline_query_current_chat=example,
        )]
        for example in i18n.MENU_EXAMPLES
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
