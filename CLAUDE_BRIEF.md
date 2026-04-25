# Riga Guide Bot — Project Brief for Claude

> **Date:** 2026-04-25 (обновлён AG после завершения M8/M9 подготовки)
> **Status:** M8 Content Seed + M9 HITL-подготовка ЗАВЕРШЕНЫ. Готовы к M9 HITL-прогону → M10 Deploy.
> **Methodology:** Molyanov (spec-driven pipeline)
> **Git коммиты (сессия 2026-04-25):**
> - `1e79f2d` feat(llm+tagger): migrate to google-genai SDK, tagger → transliteration, HITL text_pack
> - `d3a6211` fix(ingest): wikipedia scraper — защита от бесконечной рекурсии disambig
> - `a2a468f` chore(docker+seeds): pip upgrade + disambig-safe seed titles
> - `eea2aa2` chore(telemetry): mute httpx/httpcore/google_genai loggers to WARNING
> - `228bd5a` feat(hitl+deploy): smoke photos (5 Wikimedia CC) + DEPLOY.md google-genai update

---

## Текущее состояние

### ✅ Все задачи M1–M7 закрыты (с предыдущих сессий)

### ✅ M8/M9-подготовка закрыта (сессия 2026-04-25)

**AG выполнил:**
- Миграция `google-generativeai` → `google-genai` (новый SDK): `src/llm/gemini.py`
- Тagger переписан на транслит кириллицы: `src/rag/prompts/tagger.j2`
- `docs/hitl_text_pack.yaml` расширен до 18 запросов с `expected_tags`
- `tests/ingest/test_tagger.py` — тесты транслитерации (+5 кейсов)
- `ingest/seeds/riga.yaml` — проверен, 19 мест, всё в порядке
- `DEPLOY.md` — обновлён под `google-genai >= 1.0`, исправлены команды ingest
- `tests/fixtures/photos/` — 5 smoke-фото с Wikimedia Commons (CC-BY/Public Domain)
- `scripts/daily_rollup.py` — smoke-тест пройден, метрики M2/M3/M5 корректны

**Claude выполнил:**
- Зафиксировал коммиты 4 сессии AG в git
- Починил `wikipedia.py` (бесконечный disambig-loop → `auto_suggest=False`, `_depth` счётчик)
- `Dockerfile` — pip upgrade, `seeds/riga.yaml` — суффикс «(Рига)» для Памятника Свободы
- Снёс старую KB (`data/chroma/`, `data/bot.db*`) с английскими `place_id`
- Пересобрал образы `bot` и `ingest` с `google-genai`
- Sanity ingest на 3 местах — **Species: 3/3 OK**, все `place_id` транслит ✅
- **Запущен полный ingest 19 мест в фоне** (лог: `logs/ingest_full_2026-04-22.log`)

---

## Следующие шаги (M9 HITL-прогон → M10 Deploy)

### ⚡ Шаг 1 (ПЕРВОЕ ДЕЙСТВИЕ в новой сессии): проверить статус ingest

```bash
# Идёт ли контейнер?
docker ps --filter "name=riga_guide-ingest"

# Хвост лога
tail -20 logs/ingest_full_2026-04-22.log
```

Ожидаемый финал в логе:
```
pipeline.wikipedia.done   summary='Sources: 19/19 OK | Chunks: ~XXX total ...'
```

### Шаг 2: Проверить KB

```bash
docker compose run --rm ingest python -c "
import sqlite3
conn = sqlite3.connect('/app/data/bot.db')
rows = conn.execute('SELECT place_id, name_ru FROM place_coords').fetchall()
[print(r) for r in rows]
"
```
Ожидаем 19 строк с транслитными `place_id` (не `house-of-the-blackheads`, не `dome-cathedral`).

### Шаг 3: Запустить HITL

```bash
docker compose run --rm ingest python scripts/run_hitl.py \
  --text-pack docs/hitl_text_pack.yaml \
  --out logs/hitl_2026-04-25.csv
```

### Шаг 4: Критерии M8/M9 (PASS = зелено)

| Метрика | Порог |
|---------|-------|
| `status=ok` | ≥ 12/18 запросов (66%) |
| avg_latency | < 10 000 ms |
| p95 latency | < 15 000 ms |
| Прямые запросы в KB | `ok` + `place_id` совпадает с `expected_place_id` |

**Зелёные →** закрыть M8 + M9, идти в M10 Deploy.  
**Красные →** анализ причин, фикс, повторный прогон.

### M10 — Deploy (если M9 зелёный)

```bash
docker compose up -d bot
```
Smoke-тест в Telegram: «Дом Черноголовых», «Рижский замок», «Турайдский замок».

---

## Файловая структура (актуальная)

```
Riga_guide/
├── PROTOCOL.md              # Журнал разработки
├── CLAUDE_BRIEF.md          # Этот файл — handoff для Claude
├── DEPLOY.md                # ✅ Обновлён под google-genai (AG 2026-04-25)
├── README.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml           # ✅ google-genai>=1.0
├── .env.example
│
├── docs/
│   ├── USER_SPEC.md
│   ├── TECH_SPEC.md
│   ├── ARCHITECTURE.md      # ✅ Dependency map обновлена
│   ├── IMPLEMENTATION_PLAN.md
│   └── hitl_text_pack.yaml  # ✅ 18 запросов с expected_tags (AG)
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
│   │   ├── gemini.py         # ✅ МИГРИРОВАН на google-genai (AG 2026-04-16/25)
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
│   │       └── tagger.j2     # ✅ ТРАНСЛИТ (AG 2026-04-25)
│   ├── session/
│   │   ├── models.py         # ✅
│   │   └── store.py          # ✅
│   └── telemetry/
│       └── log.py            # ✅ httpx/httpcore muted to WARNING
│
├── ingest/
│   ├── __main__.py           # ✅ AG — CLI
│   ├── pipeline.py           # ✅ AG — оркестратор
│   ├── chunker.py            # ✅ AG
│   ├── tagger.py             # ✅ AG
│   ├── scrapers/
│   │   ├── wikipedia.py      # ✅ ПОЧИНЕН (disambig loop fix, Claude 2026-04-25)
│   │   └── firecrawl.py      # ✅ AG5
│   └── seeds/
│       └── riga.yaml         # ✅ 19 seed-страниц, безопасные названия
│
├── scripts/
│   ├── run_hitl.py           # ✅ AG3 — HITL runner
│   ├── daily_rollup.py       # ✅ AG4 + smoke-тест пройден
│   ├── backup.sh             # ✅ AG4
│   └── README.md
│
├── tests/
│   ├── unit/…
│   ├── ingest/
│   │   ├── test_tagger.py    # ✅ +5 кейсов транслитерации (AG 2026-04-25)
│   │   └── test_pipeline.py
│   ├── integration/…
│   └── fixtures/
│       ├── fake_gemini.py
│       └── photos/           # ✅ 5 smoke-фото Wikimedia CC (AG 2026-04-25)
│           ├── 01_dome_cathedral.jpg
│           ├── 02_blackheads.jpg
│           ├── 03_freedom_monument.jpg
│           ├── 04_riga_castle.jpg
│           └── 05_unknown.jpg
│
└── logs/
    └── ingest_full_2026-04-22.log  # ← проверить статус в начале сессии
```

---

## Ключевые API-контракты

### CLI
```bash
python -m ingest --source wikipedia --limit 5
python -m ingest --source firecrawl --urls https://latvia.travel/ru
python -m ingest --source text --title "Домский собор" --text-file dome.txt
```

### run_rag (синглтон)
```python
from src.rag.singleton import run_rag
result = await run_rag({
    "input_type": "text",  # text | photo | geo | followup
    "text": "Расскажи про Домский собор",
    "chat_id": 12345,
    "session_history": []
})
# result["status"] → ok | not_recognized | no_kb | llm_error | timeout
```

### tagger
```python
from ingest.tagger import tag_chunk
result = await tag_chunk(chunk_text, gemini_client=None)
# → {"place_id": "domskij-sobor-riga", "place_name": "Домский собор", "tags": [...], ...}
```

---

## Известные риски (на что смотреть при HITL)

1. **Tagger: разный `place_id` на разные чанки одного документа** — pipeline берёт первый. На «обзорных» статьях (Рига, Старая Рига, Югендстиль) может дать «не тот» place_id. При HITL — смотреть на эти места отдельно.
2. **Большие seeds** (Рига, Старая Рига, Сигулда, Югендстиль) — обзорные, без одного конкретного места. Если tagger выдаёт мусор — можно временно exclude из KB или пометить как `overview`.
3. **Gemini API quota** — free tier 15 RPM. Ingest на 19 мест ≈ 800 calls, ~15-25 мин. Не превышаем, но не форсировать параллелизм.

---

## Правила взаимодействия

1. **PROTOCOL.md:** после каждого блока добавлять запись с маркером 🤖 Claude Code или 🛠️ Antigravity.
2. **Тесты:** `pytest tests/` после каждого изменения кода.
3. **Не трогать `data/`** без явной необходимости — KB свежая.
4. **git pull --rebase** при конфликтах (не merge).

---

*Этот бриф содержит весь контекст для продолжения разработки с любой точки.*
