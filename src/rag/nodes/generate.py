"""
RAG node: generate — рендер generator.j2 + вызов Gemini → двухблочный ответ.

M5.7 — Claude task (дописано AG по плану Claude).
TECH_SPEC §5.2: generate — {passages, place, session_history} → {summary, story}, timeout 12s.

Использует generator.j2 (production-версия от Claude) и with_generate_retry.
Парсит двухблочный ответ: первый блок = summary, остальное = story.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, AsyncGenerator

from jinja2 import Environment, FileSystemLoader

from src.llm.retry import with_generate_retry
from src.telemetry.log import get_logger

logger = get_logger("rag.nodes.generate")


class _GenerateCapable(Protocol):
    async def generate(self, prompt: str) -> str: ...
    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]: ...


_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    keep_trailing_newline=True,
)


def _parse_two_blocks(raw: str) -> tuple[str, str]:
    """
    Разбирает ответ модели на два блока: summary и story.

    Контракт generator.j2 (Claude):
    - Первый блок (2-3 предложения) — энциклопедическая справка.
    - Отделяется от второго пустой строкой.
    - Второй блок (7-8 предложений) — живой рассказ.

    Если пустой строки нет — всё идёт в story.
    """
    text = raw.strip()
    if not text:
        return "", ""

    # Ищем первую пустую строку (разделитель блоков)
    parts = text.split("\n\n", 1)

    if len(parts) == 2:
        summary = parts[0].strip()
        story = parts[1].strip()
    else:
        # Нет пустой строки — fallback: первые 2 предложения = summary
        sentences = _split_first_sentences(text, n=2)
        if sentences:
            summary = sentences
            story = text[len(sentences):].strip()
        else:
            summary = ""
            story = text

    return summary, story


def _split_first_sentences(text: str, n: int = 2) -> str:
    """Извлекает первые n предложений из текста."""
    import re
    parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=n)
    if len(parts) > n:
        return " ".join(parts[:n])
    return ""


async def generate(
    state: dict[str, Any],
    *,
    gemini_client: _GenerateCapable,
    session_window: int = 4,
) -> dict[str, Any]:
    """
    Генерирует двухблочный ответ через Gemini.

    1. Рендерит generator.j2 с place, passages, session_history.
    2. Вызывает gemini.generate через with_generate_retry.
    3. Парсит ответ на summary + story.

    Args:
        state: RAGState с passages, place_id, place_name, session_history.
        gemini_client: GeminiClient с методом generate(prompt).
        session_window: сколько сообщений истории передавать в промпт.

    Returns:
        state с summary, story, raw_answer.
    """
    passages = state.get("passages", [])
    place_name = state.get("place_name", "Неизвестное место")
    place_id = state.get("place_id", "")
    session_history = state.get("session_history", [])

    # Подготавливаем объект place для шаблона
    place = {
        "name_ru": place_name,
        "name_original": "",
        "city": "",
        "aliases": [],
    }

    # Обрезаем историю до session_window последних сообщений
    trimmed_history = session_history[-session_window:] if session_history else []

    # Рендер промпта
    template = _jinja_env.get_template("generator.j2")
    prompt = template.render(
        place=place,
        passages=passages,
        session_history=trimmed_history,
    )

    logger.info("generate.start", place_name=place_name, passages_count=len(passages))

    try:
        stream_cb = state.get("stream_callback")
        if stream_cb and hasattr(gemini_client, "generate_stream"):
            # Stream mode
            raw_chunks = []
            async for chunk in gemini_client.generate_stream(prompt):
                raw_chunks.append(chunk)
                await stream_cb(chunk)
            raw = "".join(raw_chunks)
        else:
            # Fallback to non-streaming
            raw = await with_generate_retry(lambda: gemini_client.generate(prompt))
    except Exception as exc:
        logger.error("generate.llm_error", error=repr(exc))
        return {
            **state,
            "summary": "",
            "story": "",
            "raw_answer": "",
            "status": "llm_error",
            "error": repr(exc),
        }

    summary, story = _parse_two_blocks(raw)

    logger.info(
        "generate.ok",
        summary_len=len(summary),
        story_len=len(story),
    )

    return {
        **state,
        "summary": summary,
        "story": story,
        "raw_answer": raw,
    }
