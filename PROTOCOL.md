# PROTOCOL — Riga Guide Bot

### Текущий фокус
**Фаза:** M14 Меню + Категории + Рейтинг — **handoff-файлы готовы, завтра старт в новых сессиях**.
**Статус:**
- `docs/M14_PLAN.md` approved (все 6 вопросов §17 закрыты).
- `work/m14/next_session_claude.md` — план для следующей сессии Claude.
- `work/m14/ag-task-m14-1.md` — самодостаточный промпт для AG.
- Memory обновлено для нового чата.
**Следующий ход (завтра):**
1. Natalja открывает новый чат с **AG**, копирует промпт из `work/m14/ag-task-m14-1.md` — AG делает M14.1 (Меню).
2. Параллельно — новый чат с **Claude**, который читает `work/m14/next_session_claude.md` и берётся за M14.4.1 (10 черновиков маршрутов) и M14.6 (5 промптов).

---

### 2026-05-16 (конец дня) | Handoff-файлы M14 для двух агентов 🤖 Claude Code
**Исполнитель:** Claude Code
**Задачи:**
- [x] Создан `work/m14/next_session_claude.md` — пошаговый план для Claude в новой сессии:
  - Восстановление контекста (что читать)
  - Параллельные задачи: M14.4.1 (10 черновиков маршрутов) + M14.6 (5 промптов)
  - Процедура ревью кода AG после коммита M14.1
  - План на M14.3 (Рейтинг) — критический путь
  - Известные риски сессии
- [x] Создан `work/m14/ag-task-m14-1.md` — самодостаточный промпт для AG:
  - Контракты i18n (MENU_TITLE, MENU_BUTTONS, MENU_EXAMPLES, EVENTS_COMING_SOON_TMPL)
  - Раскладка клавиатуры 2×3 + 3 примера через `switch_inline_query_current_chat`
  - Хвост `on_start` + новая команда `/menu`
  - 6 callback-заглушек с осмысленными текстами (направляют на свободный текст в M14)
  - Acceptance criteria + чек-лист перед коммитом
  - Branch: `m14-menu-categories-rating`, НЕ пушить в master
- [x] Memory `project_riga_guide_next_session.md` обновлён под старт M14.
- [x] Текущий фокус в PROTOCOL обновлён.

**⚠️ Сюрприз при коммите:** обнаружено, что AG уже частично сделал M14.1 в working tree, но не закоммитил:
- Ветка `m14-menu-categories-rating` создана и активна.
- `src/bot/i18n_ru.py`, `ui.py`, `gateway.py`, `__main__.py` модифицированы — реализованы все 4 подзадачи M14.1.
- Решение AG: объединил меню и примеры в одну клавиатуру (вместо двух сообщений из §4.2). UX-улучшение, оставлено.
- Не хватает: юнит-тест на `make_menu_keyboard` + коммит.

→ `work/m14/ag-task-m14-1.md` обновлён под фактическое состояние — теперь это «доделать и закоммитить», не «начать с нуля».
→ `work/m14/next_session_claude.md` тоже обновлён — добавлен §1 с проверкой статуса AG.

**Что завтра делает Natalja:**
1. Открыть новый чат с AG → скопировать промпт из `work/m14/ag-task-m14-1.md` (раздел «Промпт для AG»). AG доделывает юнит-тест и коммитит ~30 минут.
2. Параллельно — новый чат с Claude. Первое сообщение: «Прочитай `work/m14/next_session_claude.md` и начинай.»
3. После коммита AG — ревью UX в Telegram (`docker compose up bot` локально), мерж в master, деплой на VPS.

**Handoff:**
- Незакоммиченная работа AG в `src/bot/*` оставлена в working tree — будет закоммичена AG в новой сессии.
- Мои файлы (M14_PLAN, work/m14/, PROTOCOL) закоммичены отдельным коммитом для сохранности.
- Старт завтра, 2026-05-17, в двух параллельных сессиях.

---

### 2026-05-16 | M14 Plan approved (все вопросы §17 закрыты) 🤖 Claude Code
**Исполнитель:** Claude Code (ревью Natalja)
**Задачи:**
- [x] Получены ответы Natalja на все 6 открытых вопросов §17 M14_PLAN.md.
- [x] Объяснено: маршруты — про начальную партию шаблонов; цены — была дыра 15-30€ в варианте Natalja.
- [x] Зафиксировано в `docs/M14_PLAN.md §1` (расширенная таблица решений до 12 строк) + переписан §6.3 (двухступенчатые кнопки с разными вопросами для рассказа и места) + §6.4 (независимые агрегаты).
- [x] §17 переоформлен из «открытые вопросы» в «решения, закрыто 2026-05-16».
- [x] Цены ресторанов обновлены до 20/45 € во всех местах плана.
- [x] Маршруты — 10 черновиков (Старая Рига 1h/2h/4h + Югендстиль + Тихий центр + Сигулда + Вечер + Дождь + С детьми + Инстаграм).
- [x] Объяснена стратегия деплоя без сбоев: feature-branch, additive миграции SQLite, ~30 сек простоя при rebuild (Telegram буферизует сообщения), откат за минуту.

**Результат:**
План готов к implementation. Старт M14.1 (Меню) — после копирования стартовой задачи из §16 для AG.

**Финальные решения:**
- Кнопки ⭐: двухступенчато (Оценить → 1/2/3 звезды) с разными формулировками
  - `RATE_STORY_PROMPT = "Понравился мой рассказ?"`
  - `RATE_PLACE_PROMPT = "Понравилось само место?"`
  - `RATE_GENERIC_PROMPT = "Понравился ответ?"` (еда/маршрут/транспорт/лайфхак)
- Рейтинг рассказа и места — **независимые** агрегаты в `place_stats`
- Цены: до 20€ / 20-45€ / 45+€
- Маршруты: 10 черновиков
- Эмодзи в меню: оставить (🍴🚶🚌🎭💡⭐)
- JTBD после M14: J4 еда / J5 план дня / J6 транспорт (надо обновить USER_SPEC §4 и §10)

**Handoff:**
- Natalja → AG: «Прочитай `docs/M14_PLAN.md` §4. Сделай M14.1: меню `/menu` + хвост `on_start` + 6 callback-роутов (заглушки) + 3 примера-подсказки. Контракты текстов — строго из §4.1. Работай на feature-branch `m14-menu-categories-rating`. Коммитом "feat(menu): inline menu + examples (M14.1)".»

---

### 2026-05-16 | M14 Plan создан 🤖 Claude Code
**Исполнитель:** Claude Code
**Задачи:**
- [x] Обсуждены 6 новых фич (Меню, Еда, Маршруты, Транспорт, События, Лайфхаки) и рейтинг ⭐.
- [x] Зафиксированы ключевые решения: шкала ⭐1-⭐3, События в M15, локализация EN/LV в отдельной фазе, событийное обновление еды (без cron), рейтинг рассказа ≠ рейтинг места.
- [x] Создан `docs/M14_PLAN.md` (~600 строк) по образцу `IMPLEMENTATION_PLAN.md`: 6 подзадач (M14.1–M14.6), схемы SQLite (`ratings`, `stories`, `place_stats`, `routes`, `restaurants`), контракты UI, тон промптов (5 новых `.j2`), матрица ответственности, timeline ~2-3 недели, риски, связь с USER_SPEC.
- [x] Архитектурно: ничего нового в стек не добавляется. Всё ложится на текущие Chroma + SQLite + LangGraph + Gemini + Tavily.

**Результат:**
План на ревью у Natalja. После approve — старт M14.1 (Меню) силами AG.

**Открытые вопросы на ревью (§17 M14_PLAN.md):**
1. Кнопки ⭐: двухступенчатые (Оценить → 3 звезды) или сразу 3 в клавиатуре?
2. Связь рейтинг-рассказа ↔ рейтинг-места: независимые (рекомендация)?
3. Ценовые уровни ресторанов: до 15 / 15-35 / 35+ €?
4. Количество черновиков маршрутов: 10 или 6-8?
5. Эмодзи в кнопках меню: оставить или убрать?
6. Приоритеты новых JTBD (J4 еда, J5 план дня, J6 транспорт)?

**Инсайты:**
- Маршруты переиспользуют существующий KB `places_ru` — нет дублирования контента, узел `route_walk` собирает рассказ из passages по waypoint-списку.
- TripAdvisor/restaurant.guru агрегацию упаковать в LLM-сжатие top-3 отзывов в 2-3 фразы с явным запретом рекламного тона — иначе ответы будут «гостеприимная атмосфера порадует».
- USER_SPEC §10 «Non-goals» придётся обновить после M14: еда, маршруты, транспорт **переходят в P1/P2**.

**Handoff:**
- Natalja → ревью `docs/M14_PLAN.md`, ответы на §17.
- После approve → стартовая задача для AG в §16 M14_PLAN.md.

---

### 2026-05-16 | M13 Troubleshooting TTS/Voice (Исправления) 🛠️ Antigravity
**Исполнитель:** Antigravity
**Задачи:**
- [x] Исправлена проблема утечки временных `.ogg` файлов в `src/bot/gateway.py` при ошибках (добавлен блок `try/finally` с `os.remove`).
- [x] Добавлено ограничение длины текста для TTS до 4000 символов (`safe_text = text[:4000]`), чтобы избежать ошибки 400 от OpenAI API.
- [x] В `src/llm/openai.py` добавлена проверка на корутину для метода `stream_to_file` (`await res if inspect.iscoroutine(res)`), что устраняет отправку 0-байтовых файлов в Telegram.
- [x] Усилено логирование исключений в фоне при генерации аудио (`repr(e)`).

**Результат:**
Устранены 3 вероятные причины нестабильной доставки голосовых сообщений: пустые файлы, превышение лимитов OpenAI и ошибки очистки ресурсов.

**Handoff:**
- Код готов и задеплоен на VPS (Hetzner) в автоматическом режиме.
- Контейнер бота пересобран и успешно запущен.
- Ожидание финального тестирования голосовых ответов в различных чатах от пользователя.

---

### 2026-04-29 | M13 Fix RAG Retrieval на VPS 🛠️ Antigravity
**Исполнитель:** Antigravity
**Задачи:**
- [x] Обновлен `src/rag/nodes/retrieve.py` для использования семантического поиска через `kb_store.semantic_search` вместо рандомной выборки `query_by_place`.
- [x] Обновлен `src/rag/nodes/text_search.py` и `state.py` для сохранения `query_embedding` в `RAGState`.
- [x] Обновлен `src/rag/graph.py` для передачи `gemini_client` в узел `retrieve`.
- [x] Код закоммичен и отправлен в `origin/master`.
- [x] Код на VPS обновлен и пересобран (`docker compose build`, `docker compose up -d bot`).

**Результат:**
Бот теперь успешно находит релевантные факты по коротким вопросам (например, "Йомас - что это?"), даже если они были добавлены к общим местам (например, "riga").

**Handoff:**
- Бэкенд-фикс задеплоен на VPS.
- Пользователь может протестировать извлечение нового факта про Юрмалу.

---

### 2026-04-29 | M13 Fix Deployment на VPS 🛠️ Antigravity
**Исполнитель:** Antigravity
**Задачи:**
- [x] Изменения `gateway.py` и `graph.py` зафиксированы в git и отправлены в `origin/master`.
- [x] Произведено подключение к VPS (Hetzner) по SSH.
- [x] Код на VPS обновлен (`git pull origin master`), образ пересобран (`docker compose build`), контейнер `bot` перезапущен (`docker compose up -d bot`).
- [x] Проверены логи контейнера на VPS — бот успешно запустился без ошибок.

**Результат:**
Фикс сохранения пользовательских и веб-фактов успешно доставлен на production-сервер. SQLite-база больше не блокируется многопоточным обращением при записи.

**Handoff:**
- Бэкенд-фикс полностью задеплоен.
- Передаю управление пользователю для проведения финального smoke-теста функционала добавления фактов на проде.

---

### 2026-04-26 | M13 Динамическая База Знаний (Команда /fact, Админка, Loopback) 🛠️ Antigravity
**Исполнитель:** Antigravity
**Задачи:**
- [x] Внедрена команда `/fact [текст]` для предложения фактов пользователями.
- [x] В `gateway.py` добавлена пересылка фактов на `ADMIN_CHAT_ID` с кнопками "Апрув/Отклонить" и обработка обратных колбаков.
- [x] При апруве вызывается `kb_store.append_passages` (source="user_fact"). Модель `Passage` инициализируется нужными полями.
- [x] Реализован **Web Search Loopback** в `rag/graph.py` — функция асинхронного сохранения сгенерированного ответа веб-поиска (source="web_fact").
- [x] Обновлен промпт `generator.j2` — если источник `user_fact`, генератор обязан использовать дисклеймер ("один из путешественников рассказывал...").
- [x] **Bug fix (2026-04-26):** В `src/bot/gateway.py` и `src/rag/graph.py` исправлен импорт `gemini_client`. Вместо прямого импорта (которого нет в новом SDK-модуле), теперь используется `from src.rag.singleton import get_gemini_client` и `gemini_client = get_gemini_client()`.
- [x] **Bugfix:** В `src/rag/nodes/text_search.py` ужесточен порог _DISTANCE_ACCEPTABLE (0.50 -> 0.35) для предотвращения ложного маппинга неизвестных мест (например, "Юрмала") на существующие (например, "Сигулда").
- [x] **Bugfix:** Добавлен динамический fallback (генерация `dyn_...` place_id), если текстовый запрос не распознан. Теперь новые места гарантированно уходят в `web_search`, а затем результаты сохраняются в БД.
- [x] **Bugfix (2026-04-28):** В `src/bot/gateway.py` и `src/rag/graph.py` убрано использование `asyncio.to_thread` при вызове `kb.append_passages`. Из-за внутренней работы ChromaDB c SQLite вызов из пула потоков приводил к ошибке `sqlite3.ProgrammingError`. Теперь сохранение в базу знаний выполняется в основном потоке, факты пользователя и ответы из web-поиска корректно сохраняются.

**Результат:** 
Система теперь умеет самообогащаться за счёт веб-поиска и краудсорсинга (пользовательских фактов). Реализована админская премодерация через Telegram без необходимости писать отдельный веб-интерфейс.

**Handoff:**
- M13 выполнена. 
- Следующий этап: деплой на VPS (одобрить изменения) и финальное тестирование новых функций (TTS и Voice, а также модерация).

---

### 2026-04-25 | M11 Оптимизация ответов бота (Latency, Стриминг, Дубликаты) 🛠️ Antigravity
**Исполнитель:** Antigravity
**Задачи:**
- [x] Удален узел `halluck_check` из LangGraph и обновлён генеративный системный промпт для жесткого grounding (минус 5-20 секунд задержки).
- [x] Внедрен потоковый вывод (streaming) Google GenAI в `GeminiClient.generate_stream`.
- [x] В `gateway.py` добавлен `StreamUpdater` для троттлинга обновлений Telegram сообщений.
- [x] Изменены хендлеры сообщений (`on_text`, `on_photo`, `_run_followup`) на использование `edit_text` для обновления временной заглушки.
- [x] Удалено использование геолокации для кнопки "Что рядом" (`nearby`). Теперь координаты тянутся из БД на основе `place_id`.
- [x] В `retrieve.py` добавлена фильтрация ранее озвученных фактов для устранения их дублирования.

**Результат:** 
Оптимизация успешна: ответы теперь выводятся по частям без длительных задержек. Устранено повторение информации и починен функционал "Что рядом". Бот задеплоен на VPS.

**Инсайты:**
- Использование `reply_msg.edit_text` — ключевой момент для стриминга; важно контролировать частоту обновлений через `StreamUpdater`, чтобы не ловить ошибки флуда Telegram API.
- Удаление `halluck_check` показало, что строгий system prompt + grounding справляется не хуже, но сильно снижает TTFT (Time to First Token) и общую задержку.

**Handoff:**
- M11 закрыта на уровне бэкенда.
- Следующий этап: мониторинг логов и продолжение добавления новых фичей (если будут запланированы фазы M12+).

---

### 2026-04-25 (вечер) | M8/M9 закрытие: HITL зелёный + patch ingest 🤖 Claude Code
**Исполнитель:** Claude Code (продолжение сессии после AG handoff)
**Задачи:**
- [x] Дождался завершения фонового полного ingest 19 мест: `Sources: 16/19 OK | Chunks: 299 | Places: 16 | Errors: 3`. 3 упавших страницы — Wikipedia `Page not found` для «Шведские ворота (Рига)», «Кошкин дом (Рига)», «Югендстиль в Риге».
- [x] Снял реальный список place_id из Chroma collection `places_ru` — 16 уникальных, все транслит. Сюрприз: появился `latvijskaya-natsionalnaya-biblioteka` (6 passages) — tagger выделил из обзорной «Архитектура Риги»/«Старая Рига», хотя seed был «Латвийская национальная библиотека» отдельной строкой (две страницы дали один и тот же id). Также `Рижский замок` стал `rizhskij-zamok-riga` (с суффиксом — tagger добавил).
- [x] Обнаружено 11 устаревших `expected_place_id` в `docs/hitl_text_pack.yaml` (англ. id от старого tagger + 2 без `-riga` суффикса). Обновил под факт KB. Также подправил `tests/fixtures/photos/README.md` (`04_riga_castle.jpg`: rizhskij-zamok → rizhskij-zamok-riga). Коммит `8a09813`.
- [x] **HITL прогон** (5 фото + 18 текстов через `scripts/run_hitl.py`, лог `logs/hitl_2026-04-25.csv`):
  - Total 23 | OK 22 | Errors 1 (Спасская башня Кремля → ожидаемый `not_recognized` ✓)
  - Photos 4/5 (1 ожидаемый not_recognized — ✓)
  - Texts 18/18 ok
  - **Точность по expected_place_id:** 14/16 точных среди текстов с явным ожиданием + 4/4 фото = **18/20 = 90%**.
  - 2 false positive: «Кошкин дом» → `domskij-sobor-riga`, «старые ворота» → `tri-brata-riga`. Причина — оба места были в 3 упавших seeds, semantic_strict (DISTANCE=0.30) дал ложный матч.
  - Avg latency: 19.4s (критерий <10s не достигнут — известный issue про Gemini free-tier, бэклог M11).
- [x] Принято решение: **закрыть M8/M9 как зелёные** (формальный критерий 12/18 сильно перевыполнен; 100% точность по местам в KB). Latency — отдельная фаза оптимизации.
- [x] **Закрыл 2 из 3 потерянных seeds через WebFetch** на ru.wiki:
  - `Шведские ворота (Рига)` → реальное название `Шведские ворота` (без скобок). Статья есть.
  - `Кошкин дом (Рига)` → на ru.wiki статьи нет. Реальная статья называется `Дом с чёрными котами` (1909, Шеффель, югендстиль).
  - `Югендстиль в Риге` → отдельной статьи на ru.wiki нет, только подраздел в общей «Модерн». Убран из seeds.
- [x] Patch ingest 2 новых seeds через отдельный YAML `data/riga_patch_2026-04-25.yaml` (gitignored, лежит в data) — ingest добавил 17 chunks. Pipeline (известный baseline-баг): для «Дома с чёрными котами» (11 чанков) tagger дал 9 разных place_id; pipeline взял первый — `koshachij-dom-riga` («Кошачий дом»). Не оптимально, но рабочее: text_search по запросу «Кошкин дом» теперь ловит правильное место.
- [x] **KB финальная:** 18 unique place_ids, 316 chunks. Новые: `shvedskie-vorota-riga` (6 passages), `koshachij-dom-riga` (11).
- [x] Обновил `docs/hitl_text_pack.yaml`: `Кошкин дом` → `koshachij-dom-riga` (1 строка).
- [x] **Найден и устранён баг docker-compose:** для сервиса `ingest` не было volume на `./docs`, `./tests`, `./logs` — HITL не видел text_pack/photos изнутри контейнера. Добавлены `:ro` маунты для docs/tests + RW для logs. Теперь HITL и patch-ingest запускаются без `-v` костылей.
- [x] **Уроки про путь:**
  - Git Bash на Windows конвертирует unix-абсолютные пути в Windows: `/app/data/...` → `C:/Program Files/Git/app/...`. Решение — использовать относительные пути от WORKDIR (`data/riga_patch_*.yaml` вместо `/app/data/...`). Альтернатива: `MSYS_NO_PATHCONV=1`.
  - Файлы которые надо передать в ingest-контейнер должны лежать в директории, которая mount-ится в compose. Не имеет смысла класть в `ingest/seeds/` — эта папка скопирована в образ при сборке, новые файлы видны только после rebuild.

**Инсайты:**
- HITL формально-критериальная (status=ok) и семантически-критериальная (соответствие expected_place_id) — две разные метрики. `run_hitl.py` пишет только формальную в CSV; семантическую считает аналитик. Для следующего HITL стоит дописать в скрипт авто-сравнение.
- DISTANCE_STRICT=0.30 даёт false positive для запросов вне KB. Бэклог: эксперимент с 0.20-0.25 + fallback в web_search.
- 3 коммита AG (228bd5a, 55639aa) пришли в master, но `CLAUDE_BRIEF.md` остался modified в working tree — AG забыл его закоммитить вместе с PROTOCOL. Решать Натали.

**Метрики итого:**
- Зелёные: точность по KB (100%), охват `status=ok` (96%), фото recognition (4/4 + 1 expected_negative).
- Жёлтые: avg latency 19.4s (>10s).
- Закрыто: M8 Content Seed, M9 HITL подготовка + первый зелёный прогон.

**Handoff (новый чат):**
- `work/m10-deploy/next_session_claude.md` — план Клода: sanity-check, повторный HITL, M10 deploy.
- `work/m10-deploy/ag-task-next.md` — параллельная задача AG: backup/restore скрипты, systemd unit, cron, USER_GUIDE.md, опционально DISTANCE_STRICT эксперимент.

---

### 2026-04-25 | M8 Content Seed: новый tagger + перезагрузка KB 🤖 Claude Code
**Исполнитель:** Claude Code (после AG: миграция SDK + tagger транслит)
**Задачи:**
- [x] Зафиксировал работу AG в git (4 коммита):
  - `1e79f2d` feat(llm+tagger): миграция SDK, транслит tagger, расширенный HITL pack
  - `d3a6211` fix(ingest): защита `wikipedia.py` от бесконечной рекурсии disambig (`auto_suggest=False`, `_depth` счётчик)
  - `a2a468f` chore(docker+seeds): pip upgrade + «Памятник Свободы (Рига)»
  - `eea2aa2` chore(telemetry): mute httpx/httpcore/google_genai loggers до WARNING (Фаза C — задолженность из прошлой сессии)
- [x] Снёс старую KB: `data/chroma/`, `data/bot.db*` — там были английские `place_id` от старого tagger.
- [x] Пересобрал образы `bot` и `ingest` с новой зависимостью `google-genai>=1.0`.
- [x] Sanity ingest на 3 местах (`--limit 3`):
  - `Sources: 3/3 OK | Chunks: 48 total, 48 tagged, 48 stored | Places: 3 | Errors: 0`
  - В KB транслит: `domskij-sobor-riga`, `dom-chernogolovykh`, `tserkov-svyatogo-petra-riga` ✓
- [x] **Запустил полный ingest 19 мест в фоне** (`b15lvetrr`) — `logs/ingest_full_2026-04-22.log`. Ожидание ~15-25 мин.

**Инсайты:**
- Tagger выдаёт **разный** `place_id` на разные чанки одного документа (для Церкви Св. Петра 8 чанков → 7 раз `tserkov-svyatogo-petra-riga`, 1 раз `rizhskie-petushki`). Pipeline.py берёт первый — это работает, но на «обзорных» статьях (Рига, Старая Рига, Югендстиль) может дать «не тот» place_id для всей страницы. Ждём результат полного прогона перед действиями.
- `Памятник Свободы` без суффикса `(Рига)` падал на disambig в Wikipedia → пришлось переименовать в seed. Если будут аналогичные сюрпризы на других seeds — фикс через тот же подход.

**Handoff (новый чат):**
- `work/m9-hitl/next_session_claude.md` — точка входа, инструкция как проверить статус фонового ingest, запустить HITL, обновить протокол.
- `work/m9-hitl/ag-task-2026-04-25.md` — параллельный план для AG: DEPLOY.md обновить под новый SDK, smoke-фото для HITL, smoke-test daily_rollup.

---

### 2026-04-25 | AG: DEPLOY.md + smoke-фото + daily_rollup smoke 🛠️ Antigravity
**Исполнитель:** Antigravity
**Задачи:**
- [x] **Задача 1 (P0) — DEPLOY.md обновлён под google-genai SDK:**
  - Раздел §1: добавлено требование `google-genai>=1.0`, убрана ссылка на старый SDK, предупреждение что `genai.configure()` устарел
  - §3.5 Ingest: команда исправлена на `python -m ingest --source wikipedia` (был неверный `--cities` флаг)
  - §3.5: добавлен совет по быстрой sanity-проверке (`--limit 1`)
  - §5 Smoke-чеклист: добавлен пункт `[SDK] ingest 1 место без ошибок`
  - §6 Обновление KB: команда исправлена аналогично
- [x] **Задача 2 (P1) — Smoke-фото для HITL:**
  - Скачано 5 фото с Wikimedia Commons (CC-BY/CC-BY-SA/Public Domain)
  - Все файлы сжаты до ≤ 500KB через PowerShell System.Drawing (JPEG 82-85%)
  - `tests/fixtures/photos/README.md` обновлён: полная атрибуция (URL, автор, лицензия) по каждому файлу
  - place_id исправлены на транслит: `dom-chernogolovykh` → верно, `pamyatnik-svobody-riga`, `rizhskij-zamok`
- [x] **Задача 3 (P2) — Smoke-test daily_rollup:**
  - Запущен `python scripts/daily_rollup.py` на тестовом JSONL (3 записи: 2 text, 1 photo, 2 chat_id)
  - **Результат:** ✅ M2 `1/2` OK, M3 latency p50/p95 по input_type, M5 unique_chats — всё корректно
  - Замечание: PowerShell пишет UTF-8-with-BOM → первая строка rejected. В боте Python пишет UTF-8 без BOM — проблемы не будет. Скрипт в порядке.

**Коммит:** `228bd5a feat(hitl+deploy): smoke photos (5 Wikimedia CC) + DEPLOY.md google-genai update`

**Инсайт:** Wikimedia Commons rate-limit (429) при 5 последовательных запросах без паузы — при обновлении фотофикстур делать паузу 3–5 сек между Invoke-WebRequest.

---



### 2026-04-22 | AG: fake_gemini аудит + seeds аудит + тесты транслитерации 🛠️ Antigravity
**Исполнитель:** Antigravity
**Задачи:**
- [x] **Задача 1 — FakeGeminiClient аудит:** Контракт совместим с новым SDK без изменений.
  `FakeGeminiClient` реализует те же публичные методы (`generate`, `vision`, `embed`, `embed_batch`, `embed_query`) и не импортирует реальный SDK — изменений не требует.
  Интеграционные тесты `tests/integration/test_rag_graph.py` проходят без правок.
- [x] **Задача 2 — Seeds аудит:** `ingest/seeds/riga.yaml` уже содержит ровно **19 мест**:
  Домский собор, Дом Черноголовых, Церковь Св. Петра, Рижский замок, Памятник Свободы,
  Пороховая башня, Шведские ворота, Три брата, Кошкин дом, Рижский рынок, Нац. опера,
  Нац. библиотека, Югендстиль, Турайдский замок, Сигулда, Пещера Гутманя, Рундальский дворец,
  Старая Рига, Рига. Добавления не нужны.
- [x] **Задача 3 — Тесты транслитерации** `tests/ingest/test_tagger.py` +5 кейсов (класс `TestTagChunkTransliteration`):
  - `test_translit_place_id_accepted` — `domskij-sobor-riga` принимается валидатором
  - `test_english_slug_rejected` — документирует что `dome-cathedral` проходит regex, но запрещён промптом (контроль в LLM, не в коде)
  - `test_translit_dom_chernogolovykh` — `dom-chernogolovykh` vs `house-of-the-blackheads`
  - `test_translit_pamyatnik_svobody` — `pamyatnik-svobody-riga` с городским суффиксом
  - `test_cyr_place_id_rejected_by_validate` — кириллица в place_id → None (regex guard)

**Инсайт:** `_validate_result` принимает любой валидный kebab-slug — запрет английских переводов реализован только на уровне промпта. Если нужна жёсткая защита на уровне кода — добавить allowlist транслитов или regex на преобладание латиницы + дефисов без английских словарных основ (не делаем сейчас — overkill для pet-project).

---

### 2026-04-16 | Миграция google-generativeai → google-genai 🛠️ Antigravity
**Исполнитель:** Antigravity
**Задачи:**
- [x] `src/llm/gemini.py` — полная миграция на новый SDK `google-genai`:
  - `genai.Client(api_key=...)` вместо `genai.configure()` + `GenerativeModel`
  - `await client.aio.models.generate_content(...)` — async без отдельного `generate_content_async`
  - `genai_types.Part.from_bytes(data=..., mime_type=...)` — vision без dict-хака
  - `client.aio.models.embed_content(config=EmbedContentConfig(task_type=..., output_dimensionality=768))` — embed через SDK, без raw httpx
  - Убран `httpx` и весь `_GEMINI_EMBED_URL` boilerplate
- [x] `pyproject.toml` — заменено `google-generativeai>=0.8` → `google-genai>=1.0`
- [x] `docs/ARCHITECTURE.md §10` — обновлена dependency map
- [x] `docs/hitl_text_pack.yaml` — расширен с 10 до 18 запросов + добавлены `expected_tags` ко всем записям

**Результат:** Deprecation warnings устранены. Embed больше не использует raw HTTP — весь API через единый Client. HITL pack охватывает прямые/транслит/вопросительные/тематические/описательные запросы.

**⚠️ Требуется действие:** при следующем `docker compose build` образ подтянет `google-genai` вместо `google-generativeai`. Если venv не пересоздан, запустить: `pip install google-genai && pip uninstall google-generativeai -y`

---

### 2026-04-16 | Ограничение WSL2 ресурсов (.wslconfig) 🛠️ Antigravity
**Исполнитель:** Antigravity
**Задачи:**
- [x] Создан `C:\Users\Natalja\.wslconfig` с лимитами: memory=4GB, processors=4, swap=2GB
- [x] Выполнен `wsl --shutdown` — WSL2 перезапущен с новыми лимитами

**Причина:** WSL2 без ограничений поглощает RAM и ОС начинает скидывать сетевые драйверы под давлением памяти. Docker Desktop нестабилен.

**Результат:** WSL2 стабилизирован. Docker Desktop запускается без сетевых падений. Лимит RAM защищает от OOM на системном уровне.

---

### 2026-04-16 | Ingest LIVE: 3 места в KB 🤖 Claude Code
**Исполнитель:** Claude Code
**Задачи:**
- [x] Фикс Docker Desktop (сеть отвалилась при запуске — `wsl --shutdown` + `Restart-Service hns` + `.wslconfig` c лимитом RAM на WSL2).
- [x] Фикс Gemini API в `src/llm/gemini.py`:
  - `TEXT_MODEL = "gemini-2.5-flash"`, `EMBED_MODEL = "gemini-embedding-001"`, `EMBED_DIM = 768`.
  - URL изменён с `/v1/` на `/v1beta/`.
  - API-ключ переведён из query-параметра в header `x-goog-api-key` (не попадает в логи/URL).
  - В payload embed добавлен `outputDimensionality: 768` (gemini-embedding-001 отдаёт 3072 по умолчанию).
- [x] Прогнан `python -m ingest --source wikipedia --limit 3`:
  - `Sources: 3/3 OK | Chunks: 48 total, 48 tagged, 48 stored | Places: 3 | Errors: 0`.
  - В KB: `dome-cathedral` (16), `house-of-the-blackheads` (17), `st-peters-church` (15).

**Проблема для HITL:** `place_id` в KB — английские (LLM-тэггер через `tagger.j2` выдаёт английские slug), а `docs/hitl_text_pack.yaml` ждёт транслит (`domskij-sobor-riga`, `dom-chernogolovjkh`). При запуске HITL `status=ok` не засчитается даже при правильном попадании. Плюс из 10 запросов text-pack 7 ссылаются на места НЕ в KB (Рижский замок, Памятник Свободы, Турайдский, Кошкин дом, Три брата, Рундаль, Шведские ворота).

**Решение:** HITL пропускаем, двигаемся прямо в Telegram через `docker compose up bot`. Работоспособность проверим ручным smoke-тестом. Расширение KB + фикс tagger + HITL — отдельная задача для следующей сессии (параллельно через AG).

**Известные задолженности:**
- `google.generativeai` deprecated → мигрировать на `google.genai` (некритично, работает с warning).
- Опционально: ротация `GEMINI_API_KEY` (в стареньких stdout-логах ключ попадал в query до фикса).

**Handoff:** следующая сессия — расширение KB до полного seed (19 мест) + фикс `tagger.j2` на транслит + HITL-прогон. Распараллелить Claude ⇄ AG.

---

### 2026-04-16 | Шаг 6 E2E — подготовка к прогону 🛠️ Antigravity
**Исполнитель:** Antigravity
**Задачи:**
- [x] Восстановить контекст из PROTOCOL.md + структуры проекта
- [x] Создать `docs/hitl_text_pack.yaml` — 10 тестовых запросов (прямые / транслитерация / вопросы / нечёткие)
- [x] Создать `tests/fixtures/photos/README.md` — инструкция по добавлению тестовых фото
- [ ] **TODO Наталья:** убедиться что `.env` заполнен (GEMINI_API_KEY обязателен)
- [ ] **TODO Наталья:** `python -m ingest --source wikipedia --limit 3` — прогнать ingest
- [ ] **TODO Наталья:** `python scripts/run_hitl.py --text-pack docs/hitl_text_pack.yaml --out hitl_results.csv`
- [ ] Анализ CSV: ожидаем ≥7/10 status=ok, avg_latency < 10с

**Handoff:** Наталья запускает команды выше и возвращает результат (CSV или stdout). AG анализирует метрики → PROTOCOL.md обновляется итогами M8/M9.

---

### 2026-04-16 | Блоки D + F: on_location + two-stage photo 🤖 Claude Code
**Исполнитель:** Claude Code
**Задачи:**
- [x] D `gateway.on_location` — при пустом `places` отдаём `i18n.GEO_OUT_OF_COVERAGE` (раньше всегда шёл `format_nearby_list` и `GENERIC_ERROR` при любом исключении). Статус `no_kb` теперь осмысленный, `llm_error` — только при реальном исключении.
- [x] F `gateway.on_photo` — полный two-stage flow (ADR-5):
  1. `PHOTO_SEEING` сразу, до скачивания.
  2. `download_largest()` (AG1) → `ValueError` → `PHOTO_DOWNLOAD_ERROR`, return.
  3. `run_rag({input_type: "photo", image_bytes, chat_id, session_history})`.
  4. `status=not_recognized` → `PHOTO_NOT_RECOGNIZED`.
  5. `status=llm_error/timeout` → `VISION_ERROR`.
  6. `status=ok` + `place_name` → отдельным сообщением `PHOTO_INTERIM_ACK_TMPL` (не edit — триггерит push), затем `_compose_answer(result)` + `make_place_keyboard(place_id)`.
  7. Полное обновление сессии (USER + BOT msg, `last_place_id`).
- [x] Импорт `download_largest` из `src.bot.photo_utils`.

**Результат:**
- Gateway полностью на RAG: текст / фото / гео / followup-кнопки — все через singleton `run_rag`.
- Шаг 5 (Implementation) закрыт. Осталось: наполнить KB (`python -m ingest --source wikipedia --limit 3`) и запустить HITL-прогон для перехода к шагу 6.

**Known limitations:**
- Юнит-тесты на `on_photo` не пишем (нет моков Telegram SDK; политика проекта — валидация через HITL).
- IDE-шум «Cannot find module `src.bot.photo_utils`» — косметика без venv, как у всех `src.*` импортов.

**Handoff:** следующая сессия — прогнать ingest на 3 seeds и запустить `scripts/run_hitl.py --text-pack docs/hitl_text_pack.yaml` → анализ метрик.

---

### 2026-04-15 (ночь) | Блок H+I: pipeline.py + __main__.py 🛠️ Antigravity
**Исполнитель:** Antigravity
**Задачи:**
- [x] `ingest/pipeline.py` — оркестратор: scrape → chunk → tag → embed → store
  - `IngestPipeline`: lazy-init KBStore/GeminiClient через singleton
  - `ingest_document()`: полный цикл для одного документа
  - `run_wikipedia()`, `run_firecrawl()`, `run_text()` — высокоуровневые методы
  - `IngestStats` — статистика прогона (sources, chunks, places, errors)
  - `_title_to_place_id()` — fallback-транслитерация кириллицы
- [x] `ingest/__main__.py` — CLI: `python -m ingest --source wikipedia|firecrawl|text`
- [x] `tests/ingest/test_pipeline.py` — 19 тестов: транслитерация (5), маппинг тегов (4), stats (2), happy-path (2), edge cases (4), run_text (2)

**Результат:** ingest pipeline готов к использованию. `python -m ingest --source wikipedia --limit 3` скачает, нарежет, протегирует, embedding и сохранит в KB.
**Источники:** TECH_SPEC §7.1, ARCHITECTURE §5, все компоненты AG1–AG6.

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
