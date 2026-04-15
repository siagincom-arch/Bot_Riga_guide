# Riga Guide Bot — Project Brief for Claude

> **Date:** 2026-04-15 (финальное обновление сессии AG)
> **Status:** Implementation phase — M6 + M7 ЗАВЕРШЕНЫ. Переходим к M8 Content Seed.
> **Methodology:** Molyanov (spec-driven pipeline)
> **Git commits:** `611dffd` → `547429c` → `5b49bec` (последний — pipeline + CLI)

---

## Текущее состояние

### ✅ Все задачи M1–M7 закрыты

### Что сделал Claude (блоки A–G):
- **A** `src/bot/i18n_ru.py` — все литералы бота
- **B** `src/rag/singleton.py` — lazy-init RAG-графа (KBStore, GeminiClient, TavilyClient)
- **C** `src/bot/gateway.py::on_text` — подключён к `run_rag()` + i18n
- **D** `src/bot/gateway.py::on_location` — geo_nearby через KBStore
- **E** `src/bot/gateway.py::on_tell_cb` — callback `tell:<place_id>`
- **F** `src/bot/gateway.py::on_photo` — двухэтапный ответ (interim ack + run_rag)
- **G** `src/bot/gateway.py::on_more_legend_cb` — callback `more_legend:<place_id>`
- RAG-граф: `src/rag/graph.py`, ноды `vision`, `text_search`, `retrieve`, `grade`, `generate`, `halluck_check`, `web_search`, `geo`
- Промпты: `generator.j2`, `halluck.j2`, `vision.j2`
- LLM клиенты: `src/llm/gemini.py`, `src/llm/tavily.py`, `src/llm/retry.py`
- Session: `src/session/store.py`, `src/session/models.py`
- KB: `src/kb/store.py`, `src/kb/models.py`
- Интеграционные тесты: `test_kb.py`, `test_rag_graph.py`, `test_session.py`

### Что сделал Antigravity (AG1–AG6 + tagger + pipeline):
- **AG1** `src/bot/photo_utils.py` — `download_largest()` + 9 тестов
- **AG2** Расширенные тесты: `test_ui.py` (23), `test_rate_limit.py` (13), `test_chunker.py` (17)
- **AG3** `scripts/run_hitl.py` — подключён к реальному `run_rag()` (не заглушка)
- **AG4** `scripts/backup.sh` + `scripts/daily_rollup.py`
- **AG5** `ingest/scrapers/wikipedia.py` + `ingest/scrapers/firecrawl.py` + `ingest/seeds/riga.yaml`
- **AG6** `DEPLOY.md`
- **Tagger** `ingest/tagger.py` + `src/rag/prompts/tagger.j2` + 18 тестов
- **Pipeline** `ingest/pipeline.py` — оркестратор scrape→chunk→tag→embed→store + 19 тестов
- **CLI** `ingest/__main__.py` — `python -m ingest --source wikipedia|firecrawl|text`

---

## Следующие шаги (M8–M10)

### M8 — Content Seed (30 пилотных мест)
1. Natalja выбирает 30 мест → `docs/pilot_places.md`
2. Прогнать `python -m ingest --source wikipedia --limit 30`
3. Тестировать качество ответов, подкрутить промпты
4. Критерий: ≥ 4/5 ответов «можно показывать гостям»

### M9 — Tests & HITL Pack
1. HITL smoke pack: 20 фото + 10 текстов (от Natalja)
2. Расширить интеграционные тесты
3. `pytest` проходит < 60 сек, recognition ≥ 70%

### M10 — Deploy
1. VPS: Docker, clone, `.env` с секретами
2. `docker compose up -d bot`
3. Smoke test из реального Telegram

---

## Ключевые контракты

### pipeline (AG — для прогона M8)
```python
from ingest.pipeline import IngestPipeline
pipeline = IngestPipeline()
stats = await pipeline.run_wikipedia(seeds_path="ingest/seeds/riga.yaml", limit=5)
# stats.summary() → "Sources: 5/5 OK | Chunks: 42 total, 42 tagged, 42 stored | Places: 5 | Errors: 0"
```

### CLI (AG — для прогона M8)
```bash
python -m ingest --source wikipedia --limit 5
python -m ingest --source firecrawl --urls https://latvia.travel/ru
python -m ingest --source text --title "Домский собор" --text-file dome.txt
```

### photo_utils
```python
from src.bot.photo_utils import download_largest
# async def download_largest(message, max_bytes=10_000_000) -> bytes
```

### tagger
```python
from ingest.tagger import tag_chunk
# async def tag_chunk(chunk_text, gemini_client=None) -> dict | None
# {place_id, place_name, tags: [str], coords: {lat,lon}|None, era: str|None}
```

### singleton
```python
from src.rag.singleton import get_rag_graph, run_rag, get_gemini_client
# run_rag(state) — async хелпер, берёт граф-синглтон
```

---

## Файловая структура (актуальная)

```
Riga_guide/
├── PROTOCOL.md              # Журнал разработки
├── CLAUDE_BRIEF.md          # Этот файл — handoff для Claude
├── DEPLOY.md                # Инструкция деплоя
├── README.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── .env.example
│
├── docs/
│   ├── USER_SPEC.md
│   ├── TECH_SPEC.md
│   ├── ARCHITECTURE.md
│   └── IMPLEMENTATION_PLAN.md
│
├── src/
│   ├── config.py
│   ├── bot/
│   │   ├── gateway.py        # ✅ Все хендлеры — Claude
│   │   ├── photo_utils.py    # ✅ AG1
│   │   ├── ui.py             # ✅ AG
│   │   ├── rate_limit.py     # ✅ AG
│   │   └── i18n_ru.py        # ✅ Claude
│   ├── kb/
│   │   ├── models.py         # ✅ Place, Passage
│   │   └── store.py          # ✅ KBStore
│   ├── llm/
│   │   ├── gemini.py         # ✅
│   │   ├── tavily.py         # ✅
│   │   └── retry.py          # ✅
│   ├── rag/
│   │   ├── graph.py          # ✅ build_graph()
│   │   ├── singleton.py      # ✅ run_rag()
│   │   ├── state.py          # ✅
│   │   ├── nodes/            # ✅ vision, text_search, retrieve, grade, generate, halluck_check, web_search, geo
│   │   └── prompts/
│   │       ├── generator.j2  # ✅
│   │       ├── halluck.j2    # ✅
│   │       ├── vision.j2     # ✅
│   │       └── tagger.j2     # ✅ AG
│   ├── session/
│   │   ├── models.py         # ✅
│   │   └── store.py          # ✅
│   └── telemetry/
│       └── log.py            # ✅
│
├── ingest/
│   ├── __main__.py           # ✅ AG — CLI
│   ├── pipeline.py           # ✅ AG — оркестратор
│   ├── chunker.py            # ✅ AG
│   ├── tagger.py             # ✅ AG
│   ├── scrapers/
│   │   ├── wikipedia.py      # ✅ AG5
│   │   └── firecrawl.py      # ✅ AG5
│   └── seeds/
│       └── riga.yaml         # 19 seed-страниц
│
├── scripts/
│   ├── run_hitl.py           # ✅ AG3 — HITL runner
│   ├── daily_rollup.py       # ✅ AG4
│   ├── backup.sh             # ✅ AG4
│   └── README.md
│
└── tests/
    ├── unit/
    │   ├── test_ui.py         # 23 теста
    │   ├── test_rate_limit.py # 13 тестов
    │   ├── test_chunker.py    # 17 тестов
    │   ├── test_photo_utils.py# 9 тестов
    │   ├── test_config.py
    │   ├── test_log.py
    │   ├── test_prompts.py
    │   └── test_retry.py
    ├── ingest/
    │   ├── test_tagger.py     # 18 тестов
    │   └── test_pipeline.py   # 19 тестов
    ├── integration/
    │   ├── test_kb.py
    │   ├── test_rag_graph.py
    │   └── test_session.py
    └── fixtures/
        └── fake_gemini.py
```

---

## Правила взаимодействия

1. **M6 + M7 полностью закрыты.** Все хендлеры, RAG-граф, pipeline — рабочие.
2. **PROTOCOL.md:** после каждого блока добавлять запись с маркером 🤖 Claude Code или 🛠️ Antigravity.
3. **Тесты:** `pytest tests/` после каждого изменения.
4. **Следующая задача:** M8 Content Seed — прогон ingest, оценка качества.

---

*Этот бриф содержит весь контекст для продолжения разработки с любой точки.*
