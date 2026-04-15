"""
Tagger — авто-классификация чанков через Gemini LLM.

M7.3 — AG task (H/I pipeline).
TECH_SPEC §7.1 step 3: tag each chunk with topic via LLM classifier.

Контракт:
    async def tag_chunk(chunk_text, gemini_client) -> dict | None

Возвращает:
    {place_id, place_name, tags: [str], coords: {lat, lon} | None, era: str | None}
    или None при невалидном JSON / пустом вводе.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from src.llm.gemini import GeminiClient
from src.telemetry.log import get_logger

logger = get_logger("ingest.tagger")

# Путь к промпт-шаблону
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "src" / "rag" / "prompts" / "tagger.j2"

# Валидные значения тегов (TECH_SPEC §3.2 PassageTopic)
VALID_TAGS = {"history", "legend", "architecture", "fact", "anecdote"}

# Обязательные поля в ответе
REQUIRED_FIELDS = {"place_id", "place_name", "tags"}


def _load_prompt_template() -> str:
    """Загружает шаблон промпта из tagger.j2."""
    if not _PROMPT_PATH.exists():
        # Fallback — ищем относительно cwd (для Docker)
        alt_path = Path("src/rag/prompts/tagger.j2")
        if alt_path.exists():
            return alt_path.read_text(encoding="utf-8")
        raise FileNotFoundError(f"Промпт tagger.j2 не найден: {_PROMPT_PATH}")

    return _PROMPT_PATH.read_text(encoding="utf-8")


def _render_prompt(chunk_text: str) -> str:
    """Рендерит промпт, подставляя текст чанка."""
    template = _load_prompt_template()
    # Простая подстановка Jinja-переменной (без полного Jinja2 — избегаем лишней зависимости)
    return template.replace("{{ chunk_text }}", chunk_text)


def _extract_json(raw: str) -> Optional[dict[str, Any]]:
    """
    Извлекает JSON из ответа модели.

    Обрабатывает:
    - Чистый JSON
    - JSON в markdown-обёртке ```json ... ```
    - JSON с trailing-текстом
    """
    text = raw.strip()

    # Убираем markdown-обёртку, если модель всё-таки добавила
    md_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if md_match:
        text = md_match.group(1).strip()

    # Ищем первый JSON-объект
    brace_start = text.find("{")
    if brace_start == -1:
        return None

    # Находим соответствующую закрывающую скобку
    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                json_str = text[brace_start : i + 1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    return None

    return None


def _validate_result(data: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Валидирует и нормализует результат от модели.

    Returns:
        Нормализованный dict или None при невалидности.
    """
    # Проверяем обязательные поля
    for field in REQUIRED_FIELDS:
        if field not in data:
            logger.warning("tagger.missing_field", field=field)
            return None

    # Валидация place_id
    place_id = str(data["place_id"]).strip()
    if not place_id or not re.match(r"^[a-z0-9\-]+$", place_id):
        logger.warning("tagger.invalid_place_id", place_id=place_id)
        return None

    # Валидация place_name
    place_name = str(data["place_name"]).strip()
    if not place_name:
        logger.warning("tagger.empty_place_name")
        return None

    # Нормализация tags — оставляем только валидные
    raw_tags = data.get("tags", [])
    if not isinstance(raw_tags, list):
        raw_tags = [str(raw_tags)]
    tags = [t for t in raw_tags if t in VALID_TAGS]
    if not tags:
        # Если модель дала невалидные теги — ставим "fact" по умолчанию
        tags = ["fact"]

    # Нормализация coords
    coords = data.get("coords")
    if coords is not None:
        if isinstance(coords, dict) and "lat" in coords and "lon" in coords:
            try:
                coords = {"lat": float(coords["lat"]), "lon": float(coords["lon"])}
            except (ValueError, TypeError):
                coords = None
        else:
            coords = None

    # Нормализация era
    era = data.get("era")
    if era is not None:
        era = str(era).strip() or None

    return {
        "place_id": place_id,
        "place_name": place_name,
        "tags": tags,
        "coords": coords,
        "era": era,
    }


async def tag_chunk(
    chunk_text: str,
    gemini_client: Optional[GeminiClient] = None,
) -> Optional[dict[str, Any]]:
    """
    Классифицирует чанк текста через Gemini LLM.

    Args:
        chunk_text: текст чанка для классификации.
        gemini_client: экземпляр GeminiClient (если None — берётся из singleton).

    Returns:
        dict с ключами {place_id, place_name, tags, coords, era}
        или None при невалидном ответе / пустом входе.
    """
    # Пустой вход → None
    if not chunk_text or not chunk_text.strip():
        logger.warning("tagger.empty_input")
        return None

    # Lazy-загрузка клиента через singleton
    if gemini_client is None:
        from src.rag.singleton import get_gemini_client
        gemini_client = get_gemini_client()

    # Рендерим промпт
    prompt = _render_prompt(chunk_text.strip())

    logger.info("tagger.classify", chunk_len=len(chunk_text))

    try:
        raw_response = await gemini_client.generate(prompt)
    except Exception as e:
        logger.error("tagger.gemini_error", error=str(e))
        return None

    # Парсим JSON из ответа
    parsed = _extract_json(raw_response)
    if parsed is None:
        logger.warning(
            "tagger.invalid_json",
            response_preview=raw_response[:200],
        )
        return None

    # Валидируем и нормализуем
    result = _validate_result(parsed)
    if result is None:
        logger.warning(
            "tagger.validation_failed",
            parsed=parsed,
        )
        return None

    logger.info(
        "tagger.ok",
        place_id=result["place_id"],
        tags=result["tags"],
    )
    return result
