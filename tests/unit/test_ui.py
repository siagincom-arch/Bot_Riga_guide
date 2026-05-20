"""
Юнит-тесты для UI форматирования и клавиатур.

M6.3 + M9.1 — AG task (AG2.1).
Расширено: полное покрытие format_answer, format_nearby_list, клавиатур.
"""

from __future__ import annotations

import pytest

from src.bot.ui import (
    format_answer,
    format_interim_ack,
    format_nearby_list,
    make_nearby_keyboard,
    make_place_keyboard,
    make_menu_keyboard,
    make_examples_keyboard,
)


# ============================================================
# format_answer
# ============================================================

class TestFormatAnswer:
    """Форматирование двухблочного ответа."""

    def test_both_blocks(self) -> None:
        """С summary и story — оба блока."""
        result = format_answer("Краткая справка.", "Длинный рассказ.")
        assert "📖 Справка" in result
        assert "🏛 История" in result
        assert "Краткая справка." in result
        assert "Длинный рассказ." in result

    def test_both_blocks_html_tags(self) -> None:
        """HTML-теги <b> присутствуют в обоих заголовках."""
        result = format_answer("summary", "story")
        assert "<b>" in result
        assert "</b>" in result

    def test_only_summary(self) -> None:
        """Только summary — без блока истории."""
        result = format_answer("Краткая.", "")
        assert "📖 Справка" in result
        assert "🏛 История" not in result

    def test_only_story(self) -> None:
        """Только story — без блока справки."""
        result = format_answer("", "Рассказ.")
        assert "📖 Справка" not in result
        assert "🏛 История" in result
        assert "Рассказ." in result

    def test_empty_both(self) -> None:
        """Пустые оба блока — дефолтный текст."""
        result = format_answer("", "")
        assert "нет информации" in result

    def test_separator_between_blocks(self) -> None:
        """Между блоками — двойной перенос строки."""
        result = format_answer("summary", "story")
        assert "\n\n" in result


# ============================================================
# format_interim_ack
# ============================================================

class TestFormatInterimAck:
    """Промежуточное сообщение."""

    def test_contains_place_name(self) -> None:
        result = format_interim_ack("Домский собор")
        assert "Домский собор" in result
        assert "📸" in result

    def test_html_bold(self) -> None:
        """Имя места выделено жирным."""
        result = format_interim_ack("Рундале")
        assert "<b>Рундале</b>" in result

    def test_contains_action(self) -> None:
        """Содержит слово о действии (собираю)."""
        result = format_interim_ack("Замок")
        assert "историю" in result.lower() or "собираю" in result.lower()


# ============================================================
# format_nearby_list
# ============================================================

class TestFormatNearbyList:
    """Список ближайших мест."""

    def test_empty_places(self) -> None:
        """Пустой список — сообщение «не нашлось»."""
        result = format_nearby_list([])
        assert "не нашлось" in result

    def test_one_place(self) -> None:
        """Одно место."""
        places = [{"name_ru": "Домский собор", "distance_m": 150.3}]
        result = format_nearby_list(places)
        assert "Домский собор" in result
        assert "150" in result
        assert "1." in result

    def test_two_places(self) -> None:
        """Два места."""
        places = [
            {"name_ru": "Домский собор", "distance_m": 150.3},
            {"name_ru": "Памятник Свободы", "distance_m": 720.0},
        ]
        result = format_nearby_list(places)
        assert "Домский собор" in result
        assert "Памятник Свободы" in result
        assert "📍" in result

    def test_three_places(self) -> None:
        """Три места — максимум по спеке."""
        places = [
            {"name_ru": "Место A", "distance_m": 50.0},
            {"name_ru": "Место B", "distance_m": 150.0},
            {"name_ru": "Место C", "distance_m": 280.0},
        ]
        result = format_nearby_list(places)
        assert "1." in result
        assert "2." in result
        assert "3." in result
        assert "Место A" in result
        assert "Место C" in result

    def test_more_than_three_truncated(self) -> None:
        """Больше трёх мест — показываются только первые 3."""
        places = [
            {"name_ru": f"Место {i}", "distance_m": float(i * 100)}
            for i in range(5)
        ]
        result = format_nearby_list(places)
        # Максимум 3 нумерованных в списке
        assert "4." not in result

    def test_contains_call_to_action(self) -> None:
        """Содержит призыв к действию."""
        places = [{"name_ru": "Собор", "distance_m": 100.0}]
        result = format_nearby_list(places)
        assert "нажмите" in result.lower() or "👇" in result


# ============================================================
# make_place_keyboard
# ============================================================

class TestMakePlaceKeyboard:
    """Клавиатура на ответ о месте."""

    def test_keyboard_has_two_buttons(self) -> None:
        kb = make_place_keyboard("dome-cathedral")
        # Первая строка — 2 кнопки
        assert len(kb.inline_keyboard) == 1
        assert len(kb.inline_keyboard[0]) == 2
        # Проверяем callback_data
        assert kb.inline_keyboard[0][0].callback_data == "more_legend:dome-cathedral"
        assert kb.inline_keyboard[0][1].callback_data == "nearby:dome-cathedral"

    def test_keyboard_is_inline_keyboard_markup(self) -> None:
        """Возвращает InlineKeyboardMarkup."""
        from telegram import InlineKeyboardMarkup
        kb = make_place_keyboard("test-place")
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_button_labels(self) -> None:
        """Кнопки содержат эмодзи и текст."""
        kb = make_place_keyboard("x")
        btn_texts = [btn.text for btn in kb.inline_keyboard[0]]
        assert any("легенда" in t.lower() for t in btn_texts)
        assert any("рядом" in t.lower() for t in btn_texts)


# ============================================================
# make_nearby_keyboard
# ============================================================

class TestMakeNearbyKeyboard:
    """Клавиатура со списком мест."""

    def test_keyboard_from_places(self) -> None:
        places = [
            {"place_id": "dome", "name_ru": "Собор", "distance_m": 100.0},
            {"place_id": "monument", "name_ru": "Памятник", "distance_m": 500.0},
        ]
        kb = make_nearby_keyboard(places)
        assert len(kb.inline_keyboard) == 2
        assert kb.inline_keyboard[0][0].callback_data == "tell:dome"
        assert kb.inline_keyboard[1][0].callback_data == "tell:monument"

    def test_keyboard_is_inline_keyboard_markup(self) -> None:
        """Возвращает InlineKeyboardMarkup."""
        from telegram import InlineKeyboardMarkup
        places = [{"place_id": "x", "name_ru": "Y", "distance_m": 10.0}]
        kb = make_nearby_keyboard(places)
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_max_three_buttons(self) -> None:
        """Не более 3 кнопок."""
        places = [
            {"place_id": f"p{i}", "name_ru": f"Place {i}", "distance_m": float(i * 100)}
            for i in range(5)
        ]
        kb = make_nearby_keyboard(places)
        assert len(kb.inline_keyboard) <= 3

    def test_button_shows_distance(self) -> None:
        """Кнопки показывают расстояние."""
        places = [{"place_id": "dome", "name_ru": "Собор", "distance_m": 123.456}]
        kb = make_nearby_keyboard(places)
        btn_text = kb.inline_keyboard[0][0].text
        assert "123" in btn_text
        assert "м" in btn_text

    def test_empty_places_empty_keyboard(self) -> None:
        """Пустой список → пустая клавиатура."""
        kb = make_nearby_keyboard([])
        assert len(kb.inline_keyboard) == 0

# ============================================================
# make_menu_keyboard
# ============================================================

class TestMakeMenuKeyboard:
    def test_returns_inline_keyboard(self):
        from telegram import InlineKeyboardMarkup
        kb = make_menu_keyboard()
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_has_three_rows_with_two_buttons(self):
        """6 категорий = 3 ряда по 2 кнопки."""
        kb = make_menu_keyboard()
        rows = kb.inline_keyboard
        assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"
        for i in range(3):
            assert len(rows[i]) == 2, f"Row {i} should have 2 buttons"

    def test_menu_callback_data(self):
        """Категории имеют правильный callback_data."""
        kb = make_menu_keyboard()
        callbacks = []
        for row in kb.inline_keyboard:
            for btn in row:
                callbacks.append(btn.callback_data)
        expected = {"menu:food", "menu:route", "menu:transport",
                    "menu:events", "menu:lifehack", "menu:top"}
        assert set(callbacks) == expected


# ============================================================
# make_examples_keyboard
# ============================================================

class TestMakeExamplesKeyboard:
    def test_returns_inline_keyboard(self):
        from telegram import InlineKeyboardMarkup
        kb = make_examples_keyboard()
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_has_three_rows_with_one_button(self):
        """3 примера = 3 ряда по 1 кнопке."""
        kb = make_examples_keyboard()
        rows = kb.inline_keyboard
        assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"
        for i in range(3):
            assert len(rows[i]) == 1, f"Row {i} should have 1 button"

    def test_examples_use_switch_inline_query(self):
        """Примеры используют switch_inline_query_current_chat, не callback_data."""
        kb = make_examples_keyboard()
        for row in kb.inline_keyboard:
            btn = row[0]
            assert btn.switch_inline_query_current_chat is not None
            assert btn.callback_data is None
