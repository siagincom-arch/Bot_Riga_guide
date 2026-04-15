# PROTOCOL — Riga Guide Bot

## Текущий фокус
**Фаза:** Implementation — M6 интеграция RAG в Gateway.
**Статус:** Claude закрыл блоки A (i18n_ru), B (rag/singleton), C (on_text), E+G (followup callbacks tell/more_legend). AG закрыл AG1–AG6.
**Следующий ход Claude:** блок D (подкрутить on_location error → GEO_OUT_OF_COVERAGE) → **блок F (two-stage photo)** — главное оставшееся → H/I (tagger + ingest pipeline).
**AG:** HITL runner подключён к реальному `run_rag()` из singleton — заглушка убрана.

---

### 2026-04-15 (ночь) | ingest/tagger.py + tagger.j2 🛠️ Antigravity
**Исполнитель:** Antigravity
**Задачи:**
- [x] `src/rag/prompts/tagger.j2` — промпт с жёстким JSON-форматом + 2 few-shot (Домский собор, Турайдский замок)
- [x] `ingest/tagger.py` — `tag_chunk(chunk_text, gemini_client) → dict | None`, _extract_json с markdown-fallback, _validate_result с нормализацией VALID_TAGS
- [x] `tests/ingest/test_tagger.py` — 18 тестов: _extract_json (5), _validate_result (8), happy-path (3), invalid-json (4), empty (3)
- [x] HITL runner подключён к реальному `run_rag()` (заглушка убрана)

**Результат:** tagger готов к использованию в ingest pipeline. Контракт: TECH_SPEC §7.1 step 3.
**Источники:** TECH_SPEC §5, §7.1, vision.j2 (как образец формата).

### 2026-04-15 (вечер) | Блоки B + C + E + G 🤖 Claude Code
**Исполнитель:** Claude Code
**Задачи:**
- [x] B `src/rag/singleton.py` — `get_rag_graph()` + `run_rag()` + `get_kb_store()/get_gemini_client()/get_tavily_client()` + `reset_cache()`. Lazy init процесс-уровневых синглтонов, конфиг из `settings` (vision_threshold, grade_threshold, top_k, nearby_radius_m).
- [x] C `gateway.on_text` — реальный RAG-вызов через `run_rag`, обработка статусов (ok/not_recognized/no_kb/llm_error/timeout), форматирование через `_compose_answer` с UNCERTAIN_MARKER, клавиатура `make_place_keyboard(place_id)`, полная интеграция с SessionStore (user msg → RAG → bot msg → upsert).
- [x] E+G `gateway._run_followup` + callback'ы `tell:` и `more_legend:` — хелпер для followup-режима графа. `more_legend` добавляет `i18n.MORE_LEGEND_PROMPT` в session_history перед запуском.
- [x] Вспомогательные функции: `_session_history_for_rag(session, limit=4)`, `_compose_answer(result)`.

**Результат:**
- Текстовый end-to-end flow работает: пользовательский запрос → RAG → ответ + кнопки.
- Callback-кнопки под ответом («🎭 Ещё легенда», «📍 Что рядом») — обе обрабатываются реально, через тот же граф с `input_type="followup"`.
- RAG-граф теперь доступен как синглтон в любом месте процесса — HITL runner AG разблокирован.

**Known limitations:**
- `on_photo` всё ещё заглушка (только `PHOTO_SEEING`). Блок F в следующей сессии.
- `on_location` при ошибке показывает `GENERIC_ERROR` — в новой сессии стоит отличать `out_of_coverage` → `GEO_OUT_OF_COVERAGE`.
- Шум IDE «Cannot find module» (косметический, нет venv — зафиксирован ранее).

**Handoff:** следующая сессия — блок F (two-stage photo в `on_photo`, использует `src.bot.photo_utils.download_largest` от AG + `run_rag` с `input_type="photo"` + `image_bytes`). См. memory `project_riga_guide_next_session.md` — там пошаговый рецепт.

---


---

### 2026-04-15 | AG1–AG6 блок задач Antigravity 🛠️ Antigravity
**Исполнитель:** Antigravity
**Задачи:**
- [x] AG1.1 `src/bot/photo_utils.py` + `tests/unit/test_photo_utils.py` — download_largest() с max_bytes проверкой, 9 тестов
- [x] AG2.1 Расширен `tests/unit/test_ui.py` — 23 теста (format_answer 6, format_interim_ack 3, format_nearby_list 6, make_place_keyboard 3, make_nearby_keyboard 5)
- [x] AG2.2 Расширен `tests/unit/test_rate_limit.py` — 13 тестов (добавлены тесты на 30 токенов, cleanup fresh)
- [x] AG2.3 Расширен `tests/unit/test_chunker.py` — 17 тестов (~1000 слов fixture, заголовки, no text lost)
- [x] AG3.1 `scripts/run_hitl.py` — HITL runner (--photos-dir, --text-pack, --out CSV), заглушка singleton
- [x] AG3.2 `scripts/README.md` — документация backup/rollup/hitl
- [x] AG4.1 `scripts/backup.sh` — rsync chroma/ + bot.db, prune >7 days
- [x] AG4.2 `scripts/daily_rollup.py` — M2/M3/M5 метрики из JSONL, markdown report
- [x] AG5.1 `ingest/scrapers/wikipedia.py` + `ingest/seeds/riga.yaml` — WikipediaScraper с disambig fallback, 19 seed-страниц
- [x] AG5.2 `ingest/scrapers/firecrawl.py` — FirecrawlScraper с SHA1-кешем в data/raw/
- [x] AG6.1 `DEPLOY.md` — полная инструкция деплоя, cron, smoke-test чеклист
- [x] `.env.example` — добавлен FIRECRAWL_API_KEY
- [x] `pyproject.toml` — добавлены pyyaml, httpx в ingest deps

**Результат:** все 11 подзадач AG1–AG6 закрыты. Тесты: 62 новых/обновлённых тест-кейса.
**Источники:** IMPLEMENTATION_PLAN.md, ARCHITECTURE.md, TECH_SPEC.md.
**Инсайты:** scraper.py монолитный (173 строки) → wiki + firecrawl отдельно. HITL runner заблокирован на singleton от Claude.

### 2026-04-15 | M6.4 i18n_ru + wiring 🤖 Claude Code
**Исполнитель:** Claude Code
**Задачи:**
- [x] A1 `src/bot/i18n_ru.py` — плоский модуль констант: команды (START/HELP/ABOUT), rate-limit, photo pipeline (SEEING/INTERIM_ACK_TMPL/NOT_RECOGNIZED/DOWNLOAD_ERROR/VISION_ERROR), text pipeline (SEARCHING_TMPL/NOT_FOUND_TMPL), geo (OUT_OF_COVERAGE/NEARBY_REQUEST), callbacks (TELL_LOADING_TMPL/MORE_LEGEND_LOADING_TMPL), LLM_ERROR, GENERIC_ERROR, UNCERTAIN_MARKER, MORE_LEGEND_PROMPT.
- [x] A2 `src/bot/gateway.py` on_start/on_help/on_about — заменил литералы на `i18n.START_GREETING/HELP_TEXT/ABOUT_TEXT`.
- [x] A3 Остальные литералы gateway'я: rate-limit → `RATE_LIMIT_HIT`, on_photo → `PHOTO_SEEING`, on_location error → `GENERIC_ERROR`, on_text → `TEXT_SEARCHING_TMPL`, callback tell → `TELL_LOADING_TMPL`, more_legend → `MORE_LEGEND_LOADING_TMPL`, nearby → `NEARBY_REQUEST`.

**Результат:**
- Весь пользовательский русский текст в `gateway.py` теперь из `i18n_ru`. Единственный источник (TECH_SPEC §11).
- Шаблоны с плейсхолдерами используют `.format()`: `TEXT_SEARCHING_TMPL.format(query=...)`, `TELL_LOADING_TMPL.format(place_name=...)` и т.п.
- `format_nearby_list` в `src/bot/ui.py` пока содержит свой текст — это UI-слой, трогать не стал (зона AG).
- TODO-комментарии в заглушках обновлены: указаны блоки C/E/F/G плана.

**Handoff:** следующий шаг — блок B, `src/rag/singleton.py` с `get_rag_graph()` (lazy init KBStore + Gemini + Tavily + build_graph, кэш).

---


---

### 2026-04-15 | M5 RAG Graph — Claude tasks 🤖 Claude Code
**Исполнитель:** Claude Code
**Задачи:**
- [x] 5.1 `src/rag/nodes/vision.py` — vision_identify: Jinja vision.j2 → Gemini Vision + `with_vision_retry` + markdown-safe JSON парсер, порог confidence, fail → status=not_recognized
- [x] 5.3 `src/rag/nodes/text_search.py` — Chroma semantic (пороги 0.30 strict / 0.50 acceptable) + rapidfuzz по `place_coords.name_ru` (пороги 90 strong / 75 acceptable), `_choose_match` комбинирует оба сигнала, возвращает candidates при неоднозначности top-2 (ADR-7)
- [x] 5.5 `src/rag/nodes/grade.py` — чистая эвристика (count/length/topic-diversity), без LLM-вызова (cost control), порог 0.4 → web_search
- [x] 5.7 `src/rag/nodes/generate.py` — рендер generator.j2 + `with_generate_retry` + двухблочный парсер (summary до первой пустой строки, далее story)
- [x] 5.8 `src/rag/nodes/halluck_check.py` — halluck.j2 → Gemini → JSON {pass, issues}, 1 регенерация при fail, иначе uncertain=True
- [x] 5.9 `src/rag/graph.py` — LangGraph StateGraph(RAGState) с условной маршрутизацией: photo→vision→text_search, geo→geo_nearby→geo_select, text/followup→text_search/retrieve; grade→generate|web_search; halluck→END|generate (retry loop)
- [x] `src/rag/state.py` — TypedDict RAGState (все поля узлов + session + итог) с total=False
- [x] 5.10 `tests/integration/test_rag_graph.py` — 4 сценария через FakeKBStore + FakeGeminiClient: текст, гео, фото-узнал, фото-не-узнал

**Результат:**
- RAG-граф закрыт. `build_graph(kb_store, gemini_client, tavily_client)` → скомпилированный граф, вызов через `graph.ainvoke(state)` или хелпер `run_rag`.
- Маршрутизация `_route_input` по `state["input_type"]`; узлы получают зависимости через `functools.partial` — граф видит только `(state) → state`.
- Цикл halluck → generate ограничен `max_retries=1` внутри `halluck_check`; после исчерпания — `uncertain=True`, ответ всё равно идёт пользователю с дисклеймером (M6.4 добавит текст дисклеймера).
- Интеграционный тест проверяет проводку графа, не KBStore (это делает M3.7). Минимальный `_FakeKBStore` реализует `semantic_search` / `query_by_place` / `geo_nearby` + in-memory SQLite для rapidfuzz fallback'а в text_search.

**Known limitations (не блокеры):**
- IDE-диагностика в новых тестах ругается «Cannot find module pytest / src.* / tests.*» — тот же косметический шум, что фиксировали в M4: локального venv нет, тесты запускаются в Docker через `pytest tests/`.
- `_FakeKBStore` в тесте перекрывает реальный KBStore (type: ignore) — сознательно, чтобы отделить проверку графа от Chroma.

**Handoff:** Claude → M6.4 (i18n_ru) + M6.6 (two-stage photo) + интеграция графа в `src/bot/gateway.py` (сейчас там TODO-заглушки). Далее tagger (M7.5) и ingest pipeline orchestration (M7.7).

---

### 2026-04-15 | M7 Ingest Pipeline — AG tasks
**Исполнитель:** Antigravity
**Задачи:**
- [x] 7.1 `ingest/scraper.py` — httpx + BeautifulSoup, специализация по доменам (Wikipedia, Latvia.travel)
- [x] 7.2 `ingest/geo.py` — Nominatim (OSM) geocoding: name → lat/lon
- [x] 7.3 `ingest/chunker.py` — рекурсивный split (абзацы → предложения → merge), 300-600 chars
- [x] 7.6 `tests/unit/test_chunker.py` — split, merge, idempotent passage_id

**Результат:**
- Полный ingest pipeline: scrape → chunk → embed-ready Passage objects
- Scraper: вежливый UA, Wikipedia denoising (infobox, reflist, toc, sup), fallback'и
- Chunker: конфигурируемый (ChunkConfig), merge маленьких чанков, sentence-aware split
- GeoEnricher: бесплатный Nominatim, для 30 мест достаточно



### 2026-04-15 | M4+M5+M6 — AG tasks (batch)
**Исполнитель:** Antigravity
**M4:**
- [x] 4.1 `src/llm/gemini.py` — async: generate, vision, embed, embed_batch, embed_query
- [x] 4.2 `src/llm/tavily.py` — async search → list[str], silent fallback
- [x] 4.5 `tests/unit/test_prompts.py` + skeleton .j2 шаблоны
**M5:**
- [x] 5.2 `src/rag/nodes/geo.py` — geo_nearby через KBStore
- [x] 5.4 `src/rag/nodes/retrieve.py` — query_by_place top-k=6
- [x] 5.6 `src/rag/nodes/web_search.py` — Tavily → merge
**M6:**
- [x] 6.1 `src/bot/__main__.py` — entry point + polling
- [x] 6.2 `src/bot/gateway.py` — on_start/help/about/photo/location/text/callback
- [x] 6.3 `src/bot/ui.py` — keyboards, HTML formatting
- [x] 6.5 `src/bot/rate_limit.py` — token bucket 30 req/min
- [x] 6.7 Session integration (lazy init + CRUD в хендлерах)
- [x] `tests/unit/test_rate_limit.py` + `test_ui.py`

**Результат:** Бот запускается, команды работают, geo pipeline полный, photo/text — заглушки (ждут RAG от Claude).

---

### 2026-04-15 | M3 Storage — AG tasks
**Исполнитель:** Antigravity
**Задачи:**
- [x] 3.1 `src/kb/models.py` — Place, Passage, City, PassageTopic, Coords (TECH_SPEC §3.1–3.2)
- [x] 3.2 `src/session/models.py` — Session, Msg, MsgRole с add_message + is_expired
- [x] 3.3 `src/session/store.py` — CRUD, TTL 24ч, окно N сообщений, auto-evict, cleanup
- [x] 3.4 `src/kb/store.py` — Chroma wrapper: upsert, semantic_search, query_by_place
- [x] 3.5 SQLite `place_coords` + haversine_distance + geo_nearby (bbox pre-filter)
- [x] 3.7 `tests/integration/test_session.py` + `test_kb.py` — 20+ тестов на tmp-базах

**Результат:**
- Passage.passage_id = sha256(place_id + source + text[:200]) — реализовано в модели (ADR-8)
- SessionStore: CRUD + auto-evict при get() + bulk cleanup_expired()
- KBStore: Chroma `places_ru` + SQLite place_coords, idempotent upsert
- Haversine: Рига-Рундале ≈ 60 км ✓, собор-памятник ≈ 700-800 м ✓
- Интеграционные тесты: 3 фикстурных места (Домский собор, Памятник Свободы, Рундале)

**Handoff:** AG → M4 LLM clients. Claude задача M3.6 де-факто закрыта — hash встроен в Passage.model_post_init().

---

### 2026-04-15 | M1.8 + M2.3 + M4.3/4.4/4.6 — Claude tasks 🤖 Claude Code
**Исполнитель:** Claude Code
**Задачи:**
- [x] M1.8 `README.md` — 15-20 строк, русский, команды запуска + ссылки на docs
- [x] M2.3 усиленный `scrub_secrets` в `src/telemetry/log.py`:
  - рекурсивный обход вложенных dict / list / tuple (секрет во вложенном словаре больше не утекает)
  - маскировка значений типа `pydantic.SecretStr` / `SecretBytes` независимо от имени ключа
  - расширен список паттернов: добавлены `AUTH`, `BEARER`, `PRIVATE_KEY`
  - 5 новых тестов в `tests/unit/test_log.py` — все 7 существующих тестов AG остаются зелёными
- [x] M3.6 подтверждён: AG уже встроил `compute_passage_id` + auto-fill в `model_post_init` в `src/kb/models.py:58-71`. Формула `sha256(place_id + source + text[:200])` совпадает с ARCHITECTURE ADR-8. Дополнительная работа не нужна.
- [x] M4.3 `src/llm/retry.py` — async retry_async + именованные политики (with_vision_retry 2 попытки, with_generate_retry без retry — cost control) по ARCHITECTURE §6. Не влезает в `gemini.py` AG — это отдельный reusable helper, RAG-узлы оборачивают LLM-вызовы сами.
- [x] M4.3 `tests/unit/test_retry.py` — 6 тестов, в т.ч. проверка экспоненциального backoff через monkeypatch asyncio.sleep
- [x] M4.4 переписал три `.j2`-шаблона в `src/rag/prompts/` на production-качество (AG положил буквальные скелеты из TECH_SPEC §6, я их довёл):
  - `generator.j2`: контракт через объект `place` со всеми полями + `passages` с topic/text_ru + опциональная `session_history`; явный запрет писать заголовки «Справка»/«История» в вывод (бот форматирует с эмодзи сам — USER_SPEC §4)
  - `halluck.j2`: явное исключение `topic=legend/anecdote` из проверки фактов + требование JSON без markdown-обёрток
  - `vision.j2`: escape-hatch для «не Латвия» (confidence=0.0) + шкала уверенности 0.5/0.7/0.9+
- [x] M4.6 `tests/fixtures/fake_gemini.py` — FakeGeminiClient (generate/vision/embed/embed_batch/embed_query) + FakeTavilyClient + детерминированный embed через sha256 → вектор [-1,1]
- [x] Переписал `tests/unit/test_prompts.py` под новый контракт промптов (AG положил тесты под старый скелет)

**Handoff:** Claude → AG для M5.2, M5.4, M5.6 (простые узлы). Claude оставляет за собой M5.1, M5.3, M5.5, M5.7–M5.10.

**Известные ограничения:**
- IDE показывает warning «Cannot find module pydantic/jinja2/pytest» в тестах — cosmetic, нет локального venv; в Docker сборке всё импортируется. Не блокер.

---

### 2026-04-15 | M2 Config + Telemetry — AG tasks
**Исполнитель:** Antigravity
**Задачи:**
- [x] 2.1 `src/config.py` — pydantic-settings, все поля из TECH_SPEC §10, SecretStr для токенов
- [x] 2.2 `src/telemetry/log.py` — structlog, JSONL output, формат записи TECH_SPEC §3.4
- [x] 2.4 `tests/unit/test_config.py` + `tests/unit/test_log.py` — 25+ тестов
- [x] Fix: PYTHONPATH `/app` (вместо `/app/src`), CMD → `python -m src.bot`

**Результат:**
- Config загружается из `.env` / env vars, валидация при импорте (fail-fast)
- Секреты маскируются в `repr(settings)` через SecretStr → "***"
- Логгер пишет валидный JSONL, по одной строке на запись
- Scrubber (базовая реализация) фильтрует TOKEN/API_KEY/SECRET/PASSWORD из log events
- `log_request()` — convenience-обёртка для формата request_log из TECH_SPEC §3.4
- `create_test_settings()` — фабрика для тестов без реального `.env`
- Единый стиль импортов: `from src.config import settings` (и в боте, и в ingest, и в тестах)

**Handoff:** AG → Claude для M2.3 (финализация scrubber, если нужна доработка)

---

### 2026-04-15 (утро) | M1 Bootstrap — AG tasks
**Исполнитель:** Antigravity
**Задачи:**
- [x] 1.2 `.gitignore` — секреты, data/, logs/, backups/, Python, IDE
- [x] 1.3 `pyproject.toml` — runtime + ingest + dev зависимости
- [x] 1.4 `.env.example` — все переменные из TECH_SPEC §10
- [x] 1.5 `Dockerfile` — multi-stage (deps → app), Python 3.12-slim
- [x] 1.6 `docker-compose.yml` — bot (always-on) + ingest (manual profile)
- [x] 1.7 Структура папок с `__init__.py` (17 файлов) + заглушки `__main__.py`

**Результат:**
- Проект полностью соответствует `ARCHITECTURE.md §4`
- `python -m src.bot` и `python -m ingest` запускаются (заглушки)
- Docker build должен проходить (acceptance criteria M1)

**Handoff:** AG → Claude для M1.8 (README.md) и M2.3 (scrubber)



## Принятые решения (2026-04-15)

| # | Вопрос | Решение |
|---|--------|---------|
| 1 | Язык бота | Только RU |
| 2 | Способ ввода | Фото + геолокация + текст (все три) |
| 3 | Тон ответов | Гибрид: 2-3 предложения энциклопедия + 7-8 предложений живой рассказчик |
| 4 | TTS / Аудио | Отложено (не в MVP) |
| 5 | Деплой | Свой VPS |
| 6 | LLM | Google Gemini |
| 7 | Объём MVP | 150-300 мест (Рига, Сигулда, Рундале)

---

## Журнал сессий

### 2026-04-14 | Старт проекта
**Задачи:**
- [x] Найти и проанализировать 15 GitHub-проектов по теме
- [x] Составить карту источников контента о Латвии (Рига, Сигулда, Рундале)
- [x] Предложить стратегию автоматизированного сбора данных
- [x] Выработать рекомендации по технологическому стеку

**Результат:**
- Найдены и классифицированы 15 релевантных проектов (4 категории)
- Составлена карта 17+ источников контента на 3 языках
- Предложены 4 метода автоматизации сбора контента
- Определён рекомендуемый стек: Python + Gemini Vision + LangGraph + Chroma
- Лучший аналог: `telegram-smartguide-bot` (Петербург, Node.js)
- Лучший архитектурный референс: `travel-guide-adaptive-rag` (Стамбул, LangGraph)

**Источники:**
- GitHub Search, Firecrawl Search
- Анализ README 15 проектов
- Web-поиск по туристическим ресурсам Латвии

**Инсайты:**
- Ни один из найденных проектов не покрывает Латвию — **нулевая конкуренция**
- Проект Discovery (#4) — наводишь камеру → AI распознаёт → описание + аудиогид — идеальный UX-референс
- rundale.net имеет отдельный раздел с легендами — уникальный контент
- VoiceMap предлагает тур «Latvian Legends & History» — отличный образец тона повествования

**Открытые вопросы:**
1. Языки бота (RU/EN/LV)
2. Способ ввода (фото / геолокация / текст)
3. Тон ответов и наличие TTS
4. Деплой и LLM провайдер
5. Объём MVP

---

### 2026-04-15 | User Spec (Молянов — шаг 2) 🤖 Claude Code
**Задачи:**
- [x] Уточнить у владельца портрет пользователя, контекст, JTBD, критерий успеха, модель монетизации
- [x] Собрать ответы в структурированный User Spec по Молянову
- [x] Создать `docs/USER_SPEC.md` (персоны, JTBD, stories, golden path, edge cases, метрики, non-goals)

**Результат:**
- Портрет: владелец + русскоязычные гости 17–70 лет, 2–3 дня в Риге
- Контекст: на улице у достопримечательности, мобильник, одна рука
- Главный JTBD: «расскажи классную историю за 3 минуты» (J1–J3 = P0)
- Критерий успеха: положительный фидбэк гостей + 5 метрик (M1–M5)
- Монетизации нет — pet-project для себя
- Non-goals зафиксированы явно (английский, TTS, маршруты, Юрмала и пр.)
- 5 открытых вопросов вынесены на ревью (§11 USER_SPEC.md)

**Источники:**
- Ответы владельца в чате (2026-04-15)
- `CLAUDE_BRIEF.md` §2 «Decisions Made»
- Методика Молянова (spec-driven pipeline)

**Инсайты:**
- «3 минуты» хорошо бьётся с текущим форматом ответа (~300–400 слов ≈ 2–3 мин чтения) — формат валидирован через JTBD
- Контекст «на улице одной рукой» → UX-приоритет на фото и геолокацию, а не на текстовые команды
- Отсутствие монетизации = свобода отрезать всё лишнее из MVP: никакой аналитики, A/B, админки

**Следующий шаг:**
- Ревью USER_SPEC.md владельцем → ответы на §11 → переход к `docs/TECH_SPEC.md`

---

### 2026-04-15 | User Spec утверждён + Tech Spec написан 🤖 Claude Code
**Задачи:**
- [x] Закрыть §11 USER_SPEC.md решениями владельца (Q1–Q5)
- [x] Распространить решения по телу спеки (Story 1, E7, Non-goals)
- [x] Написать `docs/TECH_SPEC.md` (шаг 3 методики Молянова)

**Решения владельца по §11 USER_SPEC.md:**
- Q1 Антидубль посещений — **нет** → Non-goal
- Q2 Промежуточная фото-подпись — **да** → двухэтапный ответ в Story 1 / E7
- Q3 User-contributed content — **нет** → KB только из публичных источников
- Q4 Утренний дайджест — **нет** → Non-goal
- Q5 Сессионная память — **да** → окно 10 сообщений, TTL 24 ч (см. TECH_SPEC §9)

**Результат (TECH_SPEC.md):**
- 11 компонентов системы (C1–C11) с зонами ответственности и технологиями
- Data model: `place`, `passage`, `session`, `request_log`
- Telegram-контракты: команды, обработчики сообщений, inline-кнопки
- RAG-граф на LangGraph с 8 узлами, бюджетами таймаутов и порогами confidence
- 3 промпта-скелета на русском (генератор, hallucination check, vision)
- KB pipeline: Firecrawl/Wiki → chunks → Gemini embeddings → Chroma (~1200 чанков)
- Конфигурация через `.env`, структурные JSON-логи, лимит 30 req/min на chat_id
- Performance budgets p50/p95 синхронизированы с метрикой M3 User Spec
- 4 открытых вопроса вынесены на шаг Architecture (деплой-юнит, бэкапы, ingest-cron, шиппинг логов)

**Инсайты:**
- Gemini Flash 15 RPM на free-tier хватает для личного бота, но нужен monitoring на случай, если гости активно используют — это риск, который надо держать в голове при реальной нагрузке
- Двухэтапный ответ (Q2) = полезный side-effect: даже если RAG упадёт, пользователь уже получит имя места от Vision — graceful degradation
- Сессионная память (Q5) + отсутствие антидубля (Q1) = ок, потому что рассказ про одно и то же место можно варьировать, а не блокировать

**Следующий шаг:**
- Ревью TECH_SPEC.md владельцем → ответы на §15 (4 вопроса по деплою/бэкапу/ingest/логам) → переход к `docs/ARCHITECTURE.md`

---

### 2026-04-15 | Tech Spec утверждён + Architecture написан 🤖 Claude Code
**Задачи:**
- [x] Закрыть §15 TECH_SPEC.md решениями владельца (4 дефолта приняты)
- [x] Написать `docs/ARCHITECTURE.md` (шаг 4 методики Молянова)

**Решения по §15 TECH_SPEC.md (все дефолты):**
- Деплой-юнит: один Python-процесс, один Docker-контейнер, ingest — отдельный compose-service
- Ingest: ручной `docker compose run --rm ingest ...`, без крона
- Бэкапы: host cron → `rsync data/ backups/YYYY-MM-DD/`, 7-дневное окно
- Логи: только локальный `logs/bot.jsonl`, без внешних агрегаторов

**Результат (ARCHITECTURE.md):**
- High-level-диаграмма: пользователь → контейнер → внешние API (Gemini/Tavily/Telegram)
- Deployment view: docker-compose, long polling (без webhook), shared volumes, host cron для бэкапов
- Структура проекта: `src/bot`, `src/rag`, `src/kb`, `src/session`, `src/llm`, `ingest/`, `scripts/`, `tests/`
- 5 sequence-диаграмм: photo (golden path с двухэтапным ответом), geo, text, «ещё легенда», ingest
- Failure modes + graceful degradation (Tavily down → тихий фолбек на KB only, и т.д.)
- Testing strategy: unit + integration + HITL smoke на 20 фото и 10 текстов
- Security model: trust boundary, PII = только chat_id, rate-limit 30/min
- Dependency map (Python)
- 8 ADR-записей (Architecture Decision Log)
- Operational contract: первый запуск, обновление KB, restore из бэкапа

**Инсайты:**
- Webhook vs. long polling: для пет-бота long polling проще, не надо TLS на VPS — это сэкономит минимум день настройки
- Interim-сообщение (Q2 User Spec) решено отправлять **новым сообщением**, а не edit-ом, потому что edit не триггерит push (подсказка из MCP Telegram в контексте)
- Добавил `rapidfuzz` как fallback к векторному поиску текста — embeddings плохо ловят транслит и опечатки в славянских названиях
- Idempotency ingest через `sha256(place + source + text[:200])` → можно безопасно перезапускать без дублей

**Следующий шаг:**
- Ревью ARCHITECTURE.md владельцем → переход к Implementation (шаг 5): либо `docs/IMPLEMENTATION_PLAN.md` с разбивкой на PR/milestone, либо сразу скелет кода (на выбор владельца)

---

### 2026-04-15 | Implementation Plan (Молянов — шаг 5, подготовка) 🤖 Claude Code
**Задачи:**
- [x] Создать `docs/IMPLEMENTATION_PLAN.md` с явным разделением задач между Claude Code, Antigravity и Natalja

**Результат:**
- 10 milestone: M1 Bootstrap → M2 Config+Log → M3 Storage → M4 LLM clients → M5 RAG graph → M6 Bot Gateway → M7 Ingest → M8 Content seed → M9 Tests → M10 Deploy
- Принцип разделения: AG = boilerplate/скелеты/CRUD/скрапперы; Claude = промпты, RAG-логика, русский текст, тонкие места; Natalja = ревью, контент, деплой
- Каждая milestone имеет acceptance criteria + handoff-протокол
- Матрица ответственности (§12): AG вес ≈ 10.5 сеансов, Claude ≈ 11.6, Natalja ≈ 4.8
- Параллелизм: M5 (Claude) и M6 (AG) можно делать одновременно после M4
- 6 рисков зафиксированы (§15): Gemini RPM, Firecrawl free tier, несоответствие AG-кода спеке, скучный нарратив, обрыв лимита Claude, узкость Vision
- Стартовая задача для AG сформулирована готовым промптом (§16)

**Инсайты:**
- Точки сохранения = границы milestone + каждый подшаг внутри. При обрыве лимита Claude — новая сессия поднимает PROTOCOL.md + IMPLEMENTATION_PLAN.md и понимает статус за 2 минуты
- AG полезно давать чётко огороженные задачи по файлам, чтобы агенты не перетирали работу друг друга — зоны разнесены через структуру папок
- Claude должен **ревьюить** handoff'ы от AG перед merge, потому что AG может отклониться от Tech Spec (риск R3)

**Следующий шаг:**
- Natalja передаёт Antigravity стартовый промпт из `IMPLEMENTATION_PLAN.md §16` → AG делает M1.1–M1.7 (bootstrap) → возвращает управление Claude для M1.8 (README) и M2.3 (secret scrubber)
