# Riga Guide Bot — Project Brief for Claude

> **Date:** 2026-04-15 (обновлено)
> **Status:** Implementation phase — M6 интеграция RAG в Gateway
> **Methodology:** Molyanov (spec-driven pipeline)
> **Git commit:** `611dffd` — initial commit, 86 files, 10170 insertions

---

## Текущее состояние

### Что сделал Claude (блоки A–G):
- **A** `src/bot/i18n_ru.py` — все литералы бота
- **B** `src/rag/singleton.py` — lazy-init RAG-графа (KBStore, GeminiClient, TavilyClient)
- **C** `src/bot/gateway.py::on_text` — подключён к `run_rag()` + i18n
- **E** `src/bot/gateway.py::on_tell_cb` — callback `tell:<place_id>`
- **G** `src/bot/gateway.py::on_more_legend_cb` — callback `more_legend:<place_id>`
- RAG-граф: `src/rag/graph.py`, ноды `vision`, `text_search`, `retrieve`, `grade`, `generate`, `halluck_check`, `web_search`, `geo`
- Промпты: `generator.j2`, `halluck.j2`, `vision.j2`
- LLM клиенты: `src/llm/gemini.py`, `src/llm/tavily.py`, `src/llm/retry.py`
- Session: `src/session/store.py`, `src/session/models.py`
- KB: `src/kb/store.py`, `src/kb/models.py`
- Интеграционные тесты: `test_kb.py`, `test_rag_graph.py`, `test_session.py`

### Что сделал Antigravity (блоки AG1–AG6 + tagger):
- **AG1** `src/bot/photo_utils.py` — `download_largest()` + 9 тестов
- **AG2** Расширенные тесты: `test_ui.py` (23), `test_rate_limit.py` (13), `test_chunker.py` (17)
- **AG3** `scripts/run_hitl.py` — **подключён к реальному `run_rag()`** (не заглушка)
- **AG4** `scripts/backup.sh` + `scripts/daily_rollup.py`
- **AG5** `ingest/scrapers/wikipedia.py` + `ingest/scrapers/firecrawl.py` + `ingest/seeds/riga.yaml`
- **AG6** `DEPLOY.md`
- **Tagger** `ingest/tagger.py` + `src/rag/prompts/tagger.j2` + `tests/ingest/test_tagger.py` (18 тестов)

---

## Что осталось для Claude

### Блок D — on_location (geo)
- `src/bot/gateway.py::on_location` — подключить geo_nearby ноду, использовать `i18n.GEO_OUT_OF_COVERAGE`

### Блок F — Two-stage photo flow (ГЛАВНОЕ)
- `src/bot/gateway.py::on_photo` — использовать `photo_utils.download_largest()` + vision → interim_ack → run_rag
- Двухэтапный ответ: сначала interim "📸 Собираю историю о <b>{place}</b>", потом полный ответ

### Блок H — ingest/pipeline.py
- Оркестратор: scrape → chunk → tag → embed → store
- **ВАЖНО:** `ingest/tagger.py` уже готов — использовать `tag_chunk()`
- `ingest/chunker.py` уже готов
- `ingest/scrapers/wikipedia.py` и `ingest/scrapers/firecrawl.py` — готовы

### Блок I — ingest/__main__.py
- CLI entry point: `python -m ingest --source wikipedia --cities riga`
- Связать pipeline.py с CLI argparse

---

## Ключевые контракты для Claude

### photo_utils (AG использует в блоке F)
```python
from src.bot.photo_utils import download_largest
# async def download_largest(message: Message, max_bytes=10_000_000) -> bytes
# Выбирает max(width*height) из message.photo, скачивает через Bot API
# ValueError при превышении max_bytes
```

### tagger (AG использует в блоке H)
```python
from ingest.tagger import tag_chunk
# async def tag_chunk(chunk_text: str, gemini_client=None) -> dict | None
# Возвращает: {place_id, place_name, tags: [str], coords: {lat,lon}|None, era: str|None}
# None при: пустом входе, невалидном JSON, ошибке API
# gemini_client=None → lazy-загрузка через get_gemini_client()
```

### singleton (Claude создал)
```python
from src.rag.singleton import get_rag_graph, run_rag, get_gemini_client
# run_rag(state) — async хелпер, берёт граф-синглтон
# get_gemini_client() — lazy-init Gemini клиента
```

### HITL runner (подключён)
```python
# scripts/run_hitl.py --text-pack docs/hitl_text_pack.yaml --out results.csv
# Использует run_rag() напрямую из singleton
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
├── .env.example              # Шаблон env (включая FIRECRAWL_API_KEY)
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
│   │   ├── gateway.py        # ← Claude: D, F
│   │   ├── photo_utils.py    # ✅ AG1 — download_largest()
│   │   ├── ui.py
│   │   ├── rate_limit.py
│   │   └── i18n_ru.py
│   ├── kb/
│   │   ├── models.py         # Place, Passage, PassageTopic
│   │   └── store.py          # KBStore (Chroma + SQLite)
│   ├── llm/
│   │   ├── gemini.py         # GeminiClient
│   │   ├── tavily.py         # TavilyClient
│   │   └── retry.py
│   ├── rag/
│   │   ├── graph.py          # build_graph(), run_rag()
│   │   ├── singleton.py      # get_rag_graph(), run_rag(), get_gemini_client()
│   │   ├── state.py
│   │   ├── nodes/            # vision, text_search, retrieve, grade, generate, halluck_check, web_search, geo
│   │   └── prompts/
│   │       ├── generator.j2
│   │       ├── halluck.j2
│   │       ├── vision.j2
│   │       └── tagger.j2     # ✅ AG — для ingest/tagger.py
│   ├── session/
│   │   ├── models.py
│   │   └── store.py
│   └── telemetry/
│       └── log.py
│
├── ingest/
│   ├── __main__.py           # ← Claude: блок I
│   ├── chunker.py            # ✅ готов
│   ├── tagger.py             # ✅ AG — tag_chunk()
│   ├── scraper.py            # legacy monolith (можно заменить)
│   ├── geo.py
│   ├── scrapers/
│   │   ├── wikipedia.py      # ✅ AG5 — WikipediaScraper
│   │   └── firecrawl.py      # ✅ AG5 — FirecrawlScraper
│   └── seeds/
│       └── riga.yaml         # 19 seed-страниц Wikipedia
│
├── scripts/
│   ├── run_hitl.py           # ✅ AG3 — HITL runner (→ run_rag)
│   ├── daily_rollup.py       # ✅ AG4 — M2/M3/M5 метрики
│   ├── backup.sh             # ✅ AG4 — rsync + prune
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
    │   └── test_tagger.py     # 18 тестов
    ├── integration/
    │   ├── test_kb.py
    │   ├── test_rag_graph.py
    │   └── test_session.py
    └── fixtures/
        └── fake_gemini.py
```

---

## Правила взаимодействия

1. **Не трогать файлы AG:** `photo_utils.py`, `tagger.py`, `scrapers/*.py`, `scripts/*`, `DEPLOY.md` — это зона Antigravity.
2. **Использовать контракты AG:** `download_largest()` в блоке F, `tag_chunk()` в блоке H.
3. **PROTOCOL.md:** после каждого завершённого блока добавлять запись с маркером 🤖 Claude Code.
4. **Тесты:** запускать `pytest tests/` после каждого блока.

---

*Этот бриф содержит весь контекст для продолжения разработки с любой точки.*
