# IMPLEMENTATION PLAN — Riga Guide Bot

> **Дата:** 2026-04-15
> **Фаза:** Implementation (шаг 5 из 8 по Молянову)
> **База:** `CLAUDE_BRIEF.md`, `docs/USER_SPEC.md`, `docs/TECH_SPEC.md`, `docs/ARCHITECTURE.md`
> **Команда:** Natalja (owner) + Claude Code + Antigravity

---

## 0. Как читать этот план

Каждая задача помечена исполнителем:

| Марк | Исполнитель | Что поручаем |
|------|-------------|--------------|
| 🤖 **Claude** | Claude Code | Промпты, RAG-логика, тесты смысла, русский текст, документация, тонкие места |
| 🛠️ **AG** | Antigravity | Boilerplate, скелеты, CRUD-обёртки, конфиги, скрапперы, Dockerfile, UI-хендлеры |
| 👤 **Natalja** | Владелец | Ревью, выбор контента, HITL-тестирование, деплой на VPS, секреты |

**Принцип разделения:** AG силён в «механическом» коде по чёткой спеке — он быстро генерирует boilerplate. Claude сильнее в промптах, проверке смысла, русском тексте и логике, где важен контекст Tech Spec / Architecture. Natalja — источник контентного и продуктового решения.

**Правила координации:**
1. Каждая milestone = **отдельный коммит** (или серия) — точка сохранения.
2. После завершения milestone — обновить `PROTOCOL.md`.
3. **Handoff между агентами:** когда задача готова одним, в PROTOCOL отмечается «передаю [кому] для [что]», указывается путь к артефакту.
4. Пока один агент работает — другой **не трогает** те же файлы. Зоны изолированы через структуру папок.
5. Если AG не справляется со своей задачей (застревает, делает не то) — Natalja передаёт задачу Claude с пометкой в PROTOCOL «перехватил у AG».

---

## 1. Общая последовательность (10 milestone)

```
M1 Bootstrap          → M2 Config+Log → M3 Storage   → M4 LLM clients
                                                          ↓
M7 Ingest   ←── M5 RAG graph   ←── M6 Bot Gateway ←──────┘
    ↓
M8 Content seed  →  M9 Tests  →  M10 Deploy
```

Параллелизм возможен между M5 (Claude) и M6 (AG) после завершения M4.

---

## 2. Milestone M1 — Bootstrap (скелет проекта)

**Цель:** пустой, но корректно собирающийся Docker-контейнер, git-репозиторий, все папки из `ARCHITECTURE.md §4`.

| # | Задача | Кто | Примечание |
|---|--------|-----|-----------|
| 1.1 | `git init`, первый коммит с текущей документацией | 👤 Natalja | Одноразовый шаг |
| 1.2 | `.gitignore` (`.env`, `data/`, `logs/`, `backups/`, `__pycache__`, `.venv`, etc.) | 🛠️ AG | — |
| 1.3 | `pyproject.toml` со всеми зависимостями из `ARCHITECTURE.md §10` | 🛠️ AG | Используй `uv` или `poetry` на усмотрение AG |
| 1.4 | `.env.example` со всеми переменными из `TECH_SPEC.md §10` | 🛠️ AG | Без реальных секретов |
| 1.5 | `Dockerfile` (python:3.12-slim, multi-stage build) | 🛠️ AG | Слои: deps → app |
| 1.6 | `docker-compose.yml` (services: `bot`, `ingest`) | 🛠️ AG | По `ARCHITECTURE.md §3.2` |
| 1.7 | Создать пустые папки `src/`, `ingest/`, `scripts/`, `tests/` с `__init__.py` | 🛠️ AG | Структура из `ARCHITECTURE.md §4` |
| 1.8 | `README.md` — 15-20 строк: что это, как запустить, ссылки на `docs/` | 🤖 Claude | Русский |

**Acceptance criteria:**
- `docker compose build` проходит без ошибок.
- `docker compose run --rm bot python -c "import sys; print(sys.version)"` печатает версию.
- В git-репо лежат все файлы из списка, `.env` **не** в репо.

**Handoff:** AG → PROTOCOL «M1 done, готов `Dockerfile`, передаю Claude на README».

---

## 3. Milestone M2 — Config + Telemetry

**Цель:** типизированный config-loader и JSONL-логгер со скраббингом секретов.

| # | Задача | Кто | Примечание |
|---|--------|-----|-----------|
| 2.1 | `src/config.py` — pydantic-settings, все поля из `TECH_SPEC.md §10` | 🛠️ AG | Валидация при импорте |
| 2.2 | `src/telemetry/log.py` — structlog, JSONL output в `LOG_PATH` | 🛠️ AG | Формат записи = `TECH_SPEC §3.4` |
| 2.3 | Secret scrubber в логгере: ключи содержащие `TOKEN`, `API_KEY`, `SECRET` → `***` | 🤖 Claude | Критично для безопасности |
| 2.4 | Юнит-тесты для scrubber + config валидации | 🛠️ AG | `tests/unit/test_config.py`, `test_log.py` |

**Acceptance criteria:**
- `python -c "from src.config import settings; print(settings)"` печатает конфиг (секреты маскированы).
- Логгер пишет валидный JSON, по одной строке на запись.
- Тесты `pytest tests/unit/test_config.py test_log.py` зелёные.

**Handoff:** AG → Claude для задачи 2.3; затем Claude → AG для юнит-тестов на scrubber.

---

## 4. Milestone M3 — Storage (Session + KB)

**Цель:** рабочие обёртки над SQLite и Chroma.

| # | Задача | Кто | Примечание |
|---|--------|-----|-----------|
| 3.1 | `src/kb/models.py` — pydantic `Place`, `Passage` (поля из `TECH_SPEC §3.1–3.2`) | 🛠️ AG | — |
| 3.2 | `src/session/models.py` — `Session`, `Msg` (`TECH_SPEC §3.3`) | 🛠️ AG | — |
| 3.3 | `src/session/store.py` — CRUD, TTL 24 ч, окно 10 сообщений | 🛠️ AG | SQLite schema + миграция при старте |
| 3.4 | `src/kb/store.py` — обёртка над Chroma: `upsert(place, passages)`, `query(place_id)`, `semantic_search(text)` | 🛠️ AG | Коллекция `places_ru` |
| 3.5 | SQLite-таблица `place_coords (place_id, lat, lon)` + Haversine-запрос | 🛠️ AG | Для `geo_nearby` |
| 3.6 | Идемпотентный `passage_id = sha256(place_id + source + text[:200])` в модели `Passage` | 🤖 Claude | `ARCHITECTURE.md ADR-8` |
| 3.7 | Интеграционные тесты на tmp-базах: upsert → query → delete | 🛠️ AG | `tests/integration/test_kb.py`, `test_session.py` |

**Acceptance criteria:**
- Можно записать 3 тестовых места через `ChromaStore.upsert`, сделать `semantic_search("собор")` → получить их.
- Session auto-evict удаляет записи старше 24 ч.
- Тесты зелёные.

**Handoff:** параллельно с M2, но не раньше M1.

---

## 5. Milestone M4 — LLM Clients

**Цель:** тонкие клиенты Gemini и Tavily с повторными попытками и скраббингом логов.

| # | Задача | Кто | Примечание |
|---|--------|-----|-----------|
| 4.1 | `src/llm/gemini.py` — `generate(prompt)`, `embed(text)`, `embed_batch(list)`, `vision(image_bytes, prompt)` | 🛠️ AG | Использовать `google-generativeai` |
| 4.2 | `src/llm/tavily.py` — `search(query, max_results=5)` | 🛠️ AG | Возвращает `list[str]` сниппетов |
| 4.3 | Политика retry: Vision/Generate — 1 retry с backoff, остальное — без retry | 🤖 Claude | `ARCHITECTURE.md §6` |
| 4.4 | Промпт-шаблоны `.j2` в `src/rag/prompts/`: `generator.j2`, `halluck.j2`, `vision.j2` | 🤖 Claude | Строго из `TECH_SPEC §6`, РУССКИЙ |
| 4.5 | Юнит-тест: рендеринг каждого шаблона с фикстурой даёт непустой текст | 🛠️ AG | Без вызова LLM |
| 4.6 | Мок-клиенты для тестов (`tests/fixtures/fake_gemini.py`) | 🤖 Claude | Детерминированные ответы |

**Acceptance criteria:**
- Реальный вызов `gemini.generate("скажи 'привет'")` возвращает текст (проверяется один раз руками после настройки `.env`).
- `pytest tests/unit/test_prompts.py` зелёный.
- Секреты из лога не утекают (повторная проверка scrubber'а).

**Handoff:** AG делает клиенты → Claude пишет промпты и retry-политику → AG пишет тесты рендеринга.

---

## 6. Milestone M5 — RAG Graph (Claude-heavy)

**Цель:** работающий LangGraph pipeline от входа до ответа.

| # | Задача | Кто | Примечание |
|---|--------|-----|-----------|
| 5.1 | `src/rag/nodes/vision.py` — вызов `gemini.vision` + парсинг JSON | 🤖 Claude | Confidence threshold из config |
| 5.2 | `src/rag/nodes/geo.py` — Haversine через `place_coords`, top-3 в радиусе | 🛠️ AG | Алгоритм прямолинейный |
| 5.3 | `src/rag/nodes/text_search.py` — Chroma semantic + rapidfuzz fallback | 🤖 Claude | `ARCHITECTURE.md ADR-7` |
| 5.4 | `src/rag/nodes/retrieve.py` — top-k=6 из Chroma по `place_id` | 🛠️ AG | Простой запрос |
| 5.5 | `src/rag/nodes/grade.py` — оценка достаточности контекста | 🤖 Claude | Промпт + JSON-парсинг |
| 5.6 | `src/rag/nodes/web_search.py` — обёртка вокруг Tavily + merge в контекст | 🛠️ AG | — |
| 5.7 | `src/rag/nodes/generate.py` — рендер `generator.j2` + вызов `gemini.generate` | 🤖 Claude | Сессионная память (4 последних сообщения) |
| 5.8 | `src/rag/nodes/halluck_check.py` — проверка + 1 retry, либо маркер «возможно, неточно» | 🤖 Claude | Тонкая логика |
| 5.9 | `src/rag/graph.py` — сборка LangGraph по `TECH_SPEC §5.1` | 🤖 Claude | Основной артефакт |
| 5.10 | Интеграционный тест: весь граф на 3 фикстурных местах с мок-LLM | 🤖 Claude | `tests/integration/test_rag_graph.py` |

**Acceptance criteria:**
- `graph.invoke({"input_type": "text", "query": "Домский собор"})` возвращает `{summary_ru, story_ru}`.
- Hallucination-check ловит очевидный faux-факт в фикстуре.
- Все таймауты из `TECH_SPEC §5.2` соблюдаются.

**Handoff:** AG делает 5.2, 5.4, 5.6 быстро → Claude берёт узлы со смыслом и сборку.

---

## 7. Milestone M6 — Bot Gateway (AG-heavy)

**Цель:** бот принимает сообщения и зовёт RAG.

| # | Задача | Кто | Примечание |
|---|--------|-----|-----------|
| 6.1 | `src/bot/__main__.py` — entry point, Application setup (long polling) | 🛠️ AG | `python -m bot` |
| 6.2 | `src/bot/gateway.py` — хендлеры `on_start`, `on_help`, `on_about`, `on_photo`, `on_location`, `on_text`, callbacks | 🛠️ AG | Контракты из `TECH_SPEC §4.2` |
| 6.3 | `src/bot/ui.py` — клавиатуры «🎭 Ещё легенда / 📍 Что рядом», форматирование ответа | 🛠️ AG | `TECH_SPEC §4.3` |
| 6.4 | `src/bot/i18n_ru.py` — все пользовательские строки (привет, ошибки, фолбеки) | 🤖 Claude | Единый источник |
| 6.5 | Rate-limiter per `chat_id`: 30 req/min (token bucket in-memory) | 🛠️ AG | `ARCHITECTURE §9` |
| 6.6 | Двухэтапный ответ для фото (`on_photo`): interim ack → ждём RAG → полный ответ | 🤖 Claude | Критический UX по `USER_SPEC Story 1` |
| 6.7 | Интеграция с Session Store: после каждого ответа обновляем `last_place_id`, `history` | 🛠️ AG | — |
| 6.8 | Smoke-тест руками: `/start` в реальном Telegram-чате отвечает текстом | 👤 Natalja | Нужен `TELEGRAM_BOT_TOKEN` |

**Acceptance criteria:**
- Бот запускается `docker compose up bot`, подключается к Telegram.
- `/start`, `/help`, `/about` отвечают по-русски.
- На фото, геолокацию и текст приходит хоть какой-то ответ (даже если KB пустая — «у меня нет данных»).

**Handoff:** AG → Claude для 6.4 и 6.6 → Natalja smoke-test.

---

## 8. Milestone M7 — Ingest Pipeline

**Цель:** `docker compose run --rm ingest` наполняет Chroma из реальных источников.

| # | Задача | Кто | Примечание |
|---|--------|-----|-----------|
| 7.1 | `ingest/__main__.py` — CLI с флагами `--source`, `--cities`, `--limit` | 🛠️ AG | argparse |
| 7.2 | `ingest/scrapers/wikipedia.py` — обёртка над `wikipedia` API, список seed-страниц | 🛠️ AG | RU и EN (EN как перевод) |
| 7.3 | `ingest/scrapers/firecrawl.py` — клиент Firecrawl для latvia.travel, riga.lv, rundale.net | 🛠️ AG | Возвращает markdown |
| 7.4 | `ingest/chunker.py` — разбивка по 100-400 слов, сохранение заголовков | 🛠️ AG | Алгоритм типовой |
| 7.5 | `ingest/tagger.py` — LLM-классификатор чанка в `history/legend/architecture/fact/anecdote` | 🤖 Claude | Промпт + JSON |
| 7.6 | `ingest/pipeline.py` — оркестрация: scrape → chunk → tag → embed → upsert | 🤖 Claude | Идемпотентность через `passage_id` |
| 7.7 | Отчёт в stdout после прогона: N мест, M чанков, X ошибок | 🛠️ AG | — |
| 7.8 | Юнит-тест chunker'а (фикстура → ожидаемое число чанков) | 🛠️ AG | — |

**Acceptance criteria:**
- `docker compose run --rm ingest --source wikipedia --cities riga --limit 5` добавляет 5 мест в Chroma.
- Повторный прогон той же команды печатает «0 new, 5 skipped».
- После ingest `ChromaStore.semantic_search("Домский собор")` находит запись.

**Handoff:** AG делает 7.1–7.4, 7.7, 7.8 → Claude берёт tagger и pipeline.

---

## 9. Milestone M8 — Content Seed (HITL)

**Цель:** MVP-содержательное наполнение на 30 пилотных мест.

| # | Задача | Кто | Примечание |
|---|--------|-----|-----------|
| 8.1 | Выбрать 30 pilot-мест из Старой Риги + окрестностей | 👤 Natalja | Список в `docs/pilot_places.md` |
| 8.2 | Прогнать `ingest --places <list> --source wikipedia,firecrawl` | 🤖 Claude | Выполняет, логирует |
| 8.3 | Руками проверить качество 5 ответов бота на пилотные места | 👤 Natalja | Записать проблемы |
| 8.4 | Если качество плохое — подкрутить промпт `generator.j2` или добавить источников | 🤖 Claude | Итеративно, до ≥ 4/5 «круто» |
| 8.5 | Зафиксировать в `docs/content_log.md` итоговый список и проблемы | 🤖 Claude | — |

**Acceptance criteria:**
- Бот отвечает на все 30 запросов без «у меня нет данных».
- Natalja подтверждает: ≥ 4/5 ответов «можно показывать гостям» (это и есть M1 из `USER_SPEC §8`).

**Handoff:** Natalja собирает список → Claude прогоняет → Natalja оценивает → Claude чинит → цикл до ОК.

---

## 10. Milestone M9 — Tests & HITL Pack

**Цель:** автоматические тесты для регрессий + пакет для ручной проверки.

| # | Задача | Кто | Примечание |
|---|--------|-----|-----------|
| 9.1 | Юнит-тесты на чистые функции (chunker, Haversine, prompt render, i18n lookup) | 🛠️ AG | `tests/unit/` |
| 9.2 | Интеграционный тест: полный RAG-граф на фикстуре 3 мест с мок-LLM | 🤖 Claude | Уже сделан в M5.10, расширить |
| 9.3 | HITL smoke pack: 20 фото известных мест Риги | 👤 Natalja | Файлы → `tests/fixtures/photos/` |
| 9.4 | HITL smoke pack: 10 текстовых запросов с опечатками/транслитом | 👤 Natalja | Список → `docs/hitl_text_pack.md` |
| 9.5 | `scripts/run_hitl.py` — прогон pack'а, отчёт «прошло / упало» | 🤖 Claude | Использует реальный LLM |
| 9.6 | Запустить HITL pack, зафиксировать baseline метрики M2, M3, M4 | 🤖 Claude | В `docs/baseline_metrics.md` |

**Acceptance criteria:**
- `pytest` проходит за < 60 сек без сети.
- `python scripts/run_hitl.py` печатает цифры: recognition rate ≥ 70% (цель M4 из `USER_SPEC`).

**Handoff:** AG → тесты, Natalja → фото/текст pack, Claude → runner и отчёт.

---

## 11. Milestone M10 — Deploy

**Цель:** бот работает на VPS владельца.

| # | Задача | Кто | Примечание |
|---|--------|-----|-----------|
| 10.1 | `scripts/backup.sh` — rsync + prune старше 7 дней | 🛠️ AG | shell-скрипт |
| 10.2 | `scripts/daily_rollup.py` — подсчёт M2/M3/M5 из JSONL | 🛠️ AG | stdlib only |
| 10.3 | Настроить VPS: Docker, clone repo, `.env` c секретами | 👤 Natalja | Секреты только у неё |
| 10.4 | `crontab -e` добавить ночной backup | 👤 Natalja | `0 3 * * * ...` |
| 10.5 | `docker compose up -d bot` на VPS | 👤 Natalja | — |
| 10.6 | Smoke test: `/start` с мобильного + 1 фото + 1 геолокация | 👤 Natalja | В реальном Telegram |
| 10.7 | Обновить `PROTOCOL.md`: «MVP live», зафиксировать дату | 🤖 Claude | — |

**Acceptance criteria:**
- Бот отвечает из Telegram в течение 20 сек (p50).
- `docker ps` показывает `bot` UP.
- `logs/bot.jsonl` растёт при работе.

**Handoff:** AG готовит скрипты → Natalja деплоит → Claude финализирует PROTOCOL.

---

## 12. Общая матрица ответственности

| Milestone | Antigravity | Claude Code | Natalja |
|-----------|:-----------:|:-----------:|:-------:|
| M1 Bootstrap | ●●●● | ○ | ● |
| M2 Config+Log | ●●● | ● | |
| M3 Storage | ●●●● | ● | |
| M4 LLM clients | ●●● | ●● | |
| M5 RAG graph | ● | ●●●● | |
| M6 Bot Gateway | ●●● | ●● | ● |
| M7 Ingest | ●●● | ●● | |
| M8 Content seed | | ●● | ●●● |
| M9 Tests & HITL | ●● | ●● | ●● |
| M10 Deploy | ●● | ● | ●●● |

(● = вес задач в milestone)

---

## 13. Timeline (ориентир)

Оценка в «сеансах» (один сеанс ≈ 1-2 часа активной работы одного агента).

| Milestone | AG сеансы | Claude сеансы | Natalja сеансы |
|-----------|:---------:|:-------------:|:--------------:|
| M1 | 1 | 0.2 | 0.5 |
| M2 | 1 | 0.5 | |
| M3 | 2 | 0.3 | |
| M4 | 1 | 1 | |
| M5 | 0.5 | 3 | |
| M6 | 2 | 1 | 0.3 |
| M7 | 1.5 | 1.5 | |
| M8 | | 2 | 2 |
| M9 | 1 | 1.5 | 1 |
| M10 | 0.5 | 0.3 | 1 |
| **Итого** | **~10.5** | **~11.6** | **~4.8** |

MVP реалистичен за 2-3 недели при спокойном темпе (1-2 сеанса в день).

---

## 14. Контрольные точки (milestone gates)

После каждого milestone — короткое ревью:
- Прошли acceptance criteria? [y/n]
- Обновлён `PROTOCOL.md`? [y/n]
- Сделан коммит (точка сохранения)? [y/n]
- Есть ли новые решения/допущения, которые надо вернуть в спеки? [y/n]

Если на любой вопрос «нет» — не идём дальше.

---

## 15. Риски и смягчения

| # | Риск | Вероятность | Митигация |
|---|------|:-----------:|-----------|
| R1 | Gemini Flash free tier (15 RPM) упрётся при наплыве гостей | средняя | Мониторить, при необходимости переход на paid — bulk $5/мес. хватит. |
| R2 | Firecrawl free tier закончится на ingest | средняя | Кэшировать scraped markdown в `data/raw/`, не перекачивать |
| R3 | AG сгенерирует код, не соответствующий `TECH_SPEC` | высокая в начале | Claude делает ревью handoff'а перед merge; несоответствия — назад в AG |
| R4 | Качество нарратива на пилотных местах будет «гугл-скучно» | средняя | M8 — итеративный цикл, заложено |
| R5 | Лимит Claude обрывается на сложной задаче | средняя | Коммитить каждый подшаг, `memory/project_<feature>_next_session.md` на границах milestone |
| R6 | Vision плохо узнаёт здания с нестандартных ракурсов | высокая | Геолокация как fallback, явно прописан в E1 |

---

## 16. Стартовая задача

**Прямо сейчас начинаем с M1.1–M1.7 — это чисто AG-блок.**

Natalja передаёт Antigravity:
> Прочитай `docs/ARCHITECTURE.md §4` и `docs/TECH_SPEC.md §10`. Сделай M1 из `docs/IMPLEMENTATION_PLAN.md`: bootstrap проекта — Dockerfile, docker-compose, pyproject, .env.example, .gitignore, пустую структуру папок. Коммитить одним коммитом «M1 bootstrap». README.md и промпты не трогать — их делаю я (Claude).

После этого:
> Natalja: скажи мне «M1 готов, передаю тебе README и scrubber» — я продолжу с M1.8 и M2.3.

---

## 17. Readiness Checklist

- [x] План разбит на 10 milestone
- [x] Каждая задача имеет явного исполнителя
- [x] Acceptance criteria для каждой milestone
- [x] Протокол handoff между AG и Claude
- [x] Матрица ответственности
- [x] Timeline-оценка
- [x] Риски с митигациями
- [x] Стартовая задача сформулирована
- [ ] Owner review ← **блокирует запуск M1**
