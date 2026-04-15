"""
RAG node: grade_context — оценка достаточности контекста для ответа.

M5.5 — Claude task (дописано AG по плану Claude).
TECH_SPEC §5.2: grade_context — {passages} → {grade_sufficient, grade_score}, timeout 1s.

Если контекста мало (score < threshold) — граф пойдёт в web_search.
Если контекста хватает — переходим к generate.
"""

from __future__ import annotations

from typing import Any

from src.telemetry.log import get_logger

logger = get_logger("rag.nodes.grade")

# Пороги (TECH_SPEC §5.2)
_MIN_PASSAGES = 2        # Минимум чанков для «достаточно»
_MIN_TOTAL_CHARS = 200   # Минимум символов суммарно
_THRESHOLD_SCORE = 0.4   # Порог score для web_search fallback


def _compute_grade(passages: list[dict]) -> float:
    """
    Вычисляет score достаточности контекста [0..1].

    Эвристика (без LLM — cost control):
    - Число passages: 0 → 0.0, 1 → 0.2, 2 → 0.4, 3+ → 0.6+
    - Суммарная длина: короткие → штраф
    - Разнообразие topics: 1 topic → 0, 2+ → бонус
    """
    if not passages:
        return 0.0

    count = len(passages)
    total_chars = sum(len(p.get("text_ru", "")) for p in passages)
    unique_topics = len({p.get("topic", "fact") for p in passages})

    # Базовый score от количества
    if count >= 4:
        count_score = 0.7
    elif count >= 2:
        count_score = 0.5
    elif count == 1:
        count_score = 0.2
    else:
        count_score = 0.0

    # Бонус за длину (если > 500 chars суммарно — хороший контекст)
    length_bonus = min(total_chars / 1000.0, 0.2)

    # Бонус за разнообразие topics
    topic_bonus = 0.1 if unique_topics >= 2 else 0.0

    return min(count_score + length_bonus + topic_bonus, 1.0)


async def grade_context(
    state: dict[str, Any],
    *,
    threshold: float = _THRESHOLD_SCORE,
) -> dict[str, Any]:
    """
    Оценивает, достаточен ли KB-контекст для ответа.

    Если score < threshold — граф пойдёт в web_search (условный переход).
    Если score >= threshold — переходим к generate.

    Логика без LLM-вызова — только эвристика по количеству, длине и
    разнообразию passages. Это сознательное решение: grade_context
    вызывается на каждый запрос, LLM-вызов здесь = двойная цена.

    Args:
        state: RAGState с `passages`.
        threshold: порог score для «достаточно».

    Returns:
        state с grade_sufficient (bool) и grade_score (float).
    """
    passages = state.get("passages", [])

    score = _compute_grade(passages)
    sufficient = score >= threshold

    logger.info(
        "grade.result",
        passages_count=len(passages),
        score=round(score, 3),
        sufficient=sufficient,
    )

    return {
        **state,
        "grade_sufficient": sufficient,
        "grade_score": score,
    }
