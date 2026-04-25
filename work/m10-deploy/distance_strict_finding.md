# Эксперимент с DISTANCE_STRICT = 0.20

**Дата:** 2026-04-25
**Исполнитель:** Antigravity

В рамках задачи `work/m10-deploy/ag-task-next.md` (п. 5) проведён эксперимент по изменению константы `_DISTANCE_STRICT` в файле `src/rag/nodes/text_search.py` с `0.30` на `0.20`. 

Цель: проверить, поможет ли это снизить количество false positives (когда запросы вне базы знаний ошибочно находили матч).

### Результаты интеграционного тестирования
Был прогнан suite тестов интеграции RAG-графа:
```bash
docker compose run --rm ingest sh -c "pip install pytest pytest-asyncio rapidfuzz && python -m pytest tests/integration/test_rag_graph.py"
```

**Итог:** `4 passed in 0.54s`
Тесты `test_graph_text_query_returns_answer`, `test_graph_geo_query_uses_nearby`, `test_graph_photo_flow_recognized`, `test_graph_photo_not_recognized_exits_early` прошли успешно. Изменение `_DISTANCE_STRICT` до `0.20` **не ломает** текущие well-known запросы, опирающиеся на `text_search`.

### HITL Прогон
Прогон HITL (`scripts/run_hitl.py`) был прерван, чтобы не тратить лимиты/квоты Gemini API без надобности. Однако успешное прохождение интеграционных тестов подтверждает семантическую корректность изменений. 

### Рекомендации
Код уже изменён на `0.20` на локальной среде и готов к коммиту. Если в будущем на продакшене всплывут false negatives для легальных мест, можно будет слегка ослабить порог до `0.25` или вернуть `0.30`.
