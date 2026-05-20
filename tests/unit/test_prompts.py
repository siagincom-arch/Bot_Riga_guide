"""
Юнит-тесты рендеринга промпт-шаблонов (.j2).

M4.4 (Claude) + M4.5 (AG). Тесты обновлены под контракт Claude:
- place: объект с полями name_ru, name_original, city, aliases
- passages: список объектов с .topic и .text_ru
- session_history: список объектов с .role и .text
- generator возвращает 2 блока без буквальных заголовков «Справка»/«История» —
  бот добавит форматирование (USER_SPEC §4).
"""

from __future__ import annotations

from pathlib import Path

import jinja2
import pytest


PROMPTS_DIR = Path(__file__).resolve().parents[2] / "src" / "rag" / "prompts"


@pytest.fixture
def jinja_env() -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(PROMPTS_DIR)),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )


# --- Стабы, имитирующие pydantic-модели без импорта самих моделей ---

class _Place:
    def __init__(
        self,
        name_ru: str,
        name_original: str = "",
        city: str = "riga",
        aliases: list[str] | None = None,
    ) -> None:
        self.name_ru = name_ru
        self.name_original = name_original
        self.city = city
        self.aliases = aliases or []


class _Passage:
    def __init__(self, topic: str, text_ru: str, source: str = "kb") -> None:
        self.topic = topic
        self.text_ru = text_ru
        self.source = source


class _Msg:
    def __init__(self, role: str, text: str) -> None:
        self.role = role
        self.text = text


# --- generator.j2 ---

class TestGeneratorPrompt:
    def test_renders_with_fixture(self, jinja_env: jinja2.Environment) -> None:
        template = jinja_env.get_template("generator.j2")
        result = template.render(
            place=_Place(
                name_ru="Домский собор",
                name_original="Rīgas Doms",
                aliases=["Домский", "Dome Cathedral"],
            ),
            passages=[
                _Passage("history", "Собор заложен в 1211 году епископом Альбертом."),
                _Passage("legend", "Говорят, под собором течёт подземная река."),
            ],
            session_history=[
                _Msg("user", "Расскажи про центр Риги"),
                _Msg("bot", "С чего начнём?"),
            ],
        )
        assert "Домский собор" in result
        assert "Rīgas Doms" in result
        assert "1211" in result
        assert "подземная река" in result
        # Инструкции для модели на месте
        assert "СТРОГО" in result
        assert "Запрещено" in result

    def test_renders_with_empty_history(self, jinja_env: jinja2.Environment) -> None:
        template = jinja_env.get_template("generator.j2")
        result = template.render(
            place=_Place(name_ru="Памятник Свободы"),
            passages=[_Passage("fact", "42-метровая колонна, 1935 год.")],
            session_history=[],
        )
        assert "Памятник Свободы" in result
        assert "1935" in result
        # Пустая history → секция не печатается
        assert "Недавний диалог" not in result

    def test_minimal_place_without_original_and_aliases(
        self, jinja_env: jinja2.Environment
    ) -> None:
        template = jinja_env.get_template("generator.j2")
        result = template.render(
            place=_Place(name_ru="Три брата"),
            passages=[_Passage("architecture", "Старейший жилой комплекс.")],
            session_history=[],
        )
        assert "Три брата" in result
        assert "Оригинальное название" not in result
        assert "Другие названия" not in result

    def test_passage_topic_is_rendered(self, jinja_env: jinja2.Environment) -> None:
        """Тег topic виден в промпте — помогает LLM отличать факты от легенд."""
        template = jinja_env.get_template("generator.j2")
        result = template.render(
            place=_Place(name_ru="Кошкин дом"),
            passages=[_Passage("anecdote", "Кошки на крыше повёрнуты хвостами к гильдии.")],
            session_history=[],
        )
        assert "[anecdote]" in result


# --- vision.j2 ---

class TestVisionPrompt:
    def test_renders(self, jinja_env: jinja2.Environment) -> None:
        template = jinja_env.get_template("vision.j2")
        result = template.render()
        assert "Латвии" in result
        assert "confidence" in result
        assert "name_ru" in result

    def test_has_not_latvia_escape_hatch(self, jinja_env: jinja2.Environment) -> None:
        """Промпт учит модель возвращать confidence=0.0 если это не Латвия."""
        template = jinja_env.get_template("vision.j2")
        result = template.render()
        assert "не Латвия" in result


# --- Sanity ---

class TestAllTemplatesExist:
    @pytest.mark.parametrize("name", ["generator.j2", "vision.j2"])
    def test_template_file_exists(self, name: str) -> None:
        path = PROMPTS_DIR / name
        assert path.exists(), f"Шаблон {name} не найден в {PROMPTS_DIR}"
