# Riga Guide — точка входа для нового чата Claude

**Дата:** 2026-04-25 (сессия продолжается из предыдущего чата).
**Фаза:** M8 Content Seed → M9 HITL.
**Цель сессии:** запустить HITL с зелёными метриками (≥12/18 ok, avg_latency < 10s) и закрыть M8 + M9, чтобы перейти к шагу 7 (DEPLOY.md).

---

## 0. Что уже сделано в этой сессии (4 коммита)

```
eea2aa2 chore(telemetry): mute httpx/httpcore/google_genai loggers to WARNING
a2a468f chore(docker+seeds): pip upgrade + disambig-safe seed titles
d3a6211 fix(ingest): wikipedia scraper — защита от бесконечной рекурсии disambig
1e79f2d feat(llm+tagger): migrate to google-genai SDK, tagger → transliteration, HITL text_pack
```

Список изменений:
- AG мигрировал `google-generativeai` → `google-genai` (новый SDK) в `src/llm/gemini.py`.
- AG переписал `src/rag/prompts/tagger.j2` на **транслит** кириллицы (`dom-chernogolovykh`, `domskij-sobor-riga` вместо англ. эквивалентов).
- AG расширил `docs/hitl_text_pack.yaml` до 18 запросов с `expected_tags`.
- AG добавил тесты транслитерации в `tests/ingest/test_tagger.py`.
- Claude закоммитил всё, починил `wikipedia.py` (защита от бесконечного disambig-loop), `Dockerfile` (`pip upgrade`), `seeds/riga.yaml` («Памятник Свободы (Рига)»), `src/telemetry/log.py` (mute httpx/httpcore до WARNING).
- Старая KB снесена (`data/chroma/`, `data/bot.db*`).
- Docker-образы `bot` и `ingest` пересобраны с новой зависимостью.
- **Sanity ingest на 3 местах прошёл успешно** — все `place_id` транслит:
  - `domskij-sobor-riga` → «Домский собор»
  - `dom-chernogolovykh` → «Дом Черноголовых»
  - `tserkov-svyatogo-petra-riga` → «Церковь Святого Петра»

---

## 1. Куда мы остановились

**Полный ingest на 19 местах запущен в фоне** в предыдущем чате (background task `b15lvetrr`).
Лог пишется в `logs/ingest_full_2026-04-22.log` (Note: имя файла оставлено по дате запуска).

Фоновая задача из старого чата **не видна** в новом чате — её надо проверить через docker и/или хвост лог-файла.

---

## 2. Первое действие в новом чате

**Проверить статус полного ingest:**

```bash
# 1. Идёт ли ingest-контейнер?
docker ps --filter "name=riga_guide-ingest"

# 2. Хвост лога
tail -20 logs/ingest_full_2026-04-22.log
```

**Возможные исходы:**

### A. Ingest ещё идёт (контейнер запущен, в логе нет `pipeline.wikipedia.done`)
- Подождать через `Monitor` или просто `tail -f` (но без блокировки).
- 19 мест = ~15-25 минут от старта (~10:59 UTC времени старого чата).

### B. Ingest завершился успешно
В логе должна быть строка примерно такого вида:
```
pipeline.wikipedia.done   summary='Sources: 19/19 OK | Chunks: ~XXX total, ~XXX tagged, ~XXX stored | Places: 19 | Errors: 0'
```
И финальный блок:
```
============================================================
📊 Sources: 19/19 OK | ...
============================================================
```

**Команда проверки KB:**
```bash
docker compose run --rm ingest python -c "import sqlite3; conn = sqlite3.connect('/app/data/bot.db'); rows = conn.execute('SELECT place_id, name_ru FROM place_coords').fetchall(); [print(r) for r in rows]"
```
Ожидаем 19 строк, все `place_id` — транслит латиница (без англицизмов вроде `house-of-the-blackheads`, `dome-cathedral`).

### C. Ingest упал с ошибками
Прочитать лог, разобраться, починить (скорее всего — disambig loop на каком-то seed → добавить `(Рига)` суффикс). Перезапустить только проблемные места через `--source text` или прогнать ingest заново после фикса.

---

## 3. Запуск HITL

После того, как KB наполнена 19 местами:

```bash
docker compose run --rm ingest python scripts/run_hitl.py \
  --text-pack docs/hitl_text_pack.yaml \
  --out logs/hitl_2026-04-25.csv
```

Скрипт прогонит 18 запросов из `docs/hitl_text_pack.yaml` через RAG-граф и запишет CSV с колонками: `input, input_type, place_id, status, latency_ms, recognized_confidence`.

---

## 4. Критерии M8/M9

- **≥12/18** запросов со `status=ok` (66% покрытие).
- **avg_latency < 10000ms** (10 секунд).
- **p95 latency < 15000ms**.
- На прямые запросы из KB («Домский собор», «Дом Черноголовых», «Церковь Святого Петра», «Рижский замок», «Памятник Свободы (Рига)», «Турайдский замок») — **ok**, причём `place_id` совпадает с `expected_place_id` из text_pack.

Если зелёные → закрываем M8 + M9, идём в шаг 7 (DEPLOY.md финализация).
Если красные → анализ причин, фикс, повторный прогон.

---

## 5. Финальные шаги сессии

1. Закоммитить любые правки кода/конфига (если были).
2. Обновить `PROTOCOL.md` итогами M8/M9.
3. Обновить memory `project_riga_guide_next_session.md` — следующая фаза.
4. Если HITL зелёный — запустить бота: `docker compose up -d bot` и сделать ручной smoke-тест в Telegram («Дом Черноголовых», «Рижский замок», «Турайдский замок»).

---

## 6. Известные риски / на что смотреть

- **Tagger выдаёт разный `place_id` на разные чанки одного документа** — pipeline.py берёт первый. На длинных статьях (Рига, Старая Рига, Югендстиль) это может дать «не тот» place_id для всей страницы. Если такое всплывёт в HITL — обсудить с Natalja: либо majority vote по чанкам, либо использовать заголовок документа как наводящую подсказку для tagger.
- **Большие seeds** (`Рига`, `Старая Рига`, `Сигулда`, `Югендстиль в Риге`) — это «обзорные» страницы без одного конкретного места. Tagger может выдать что-то странное. Возможно стоит отметить их в seeds как «overview» и обрабатывать иначе. Пока — просто посмотреть что получилось в KB.
- **Quota Gemini API** — на 19 местах × ~20 чанков ~= 400 запросов на tag + 400 на embed ≈ 800 calls. Free tier — 15 RPM. Ingest по сути идёт sequentially, поэтому не превышаем, но если Tagger прокачает по 2-3 секунды на чанк — итого 15-20 минут.
- **Сессия старого чата** оставила фоновую задачу `b15lvetrr` (полный ingest). После её завершения docker compose run контейнер сам удалится (`--rm`). Никаких ручных cleanup-ов не нужно.

---

## 7. Полезные ссылки

- `PROTOCOL.md` — журнал работы.
- `work/m9-hitl/ag-task-2026-04-25.md` — параллельный план для AG.
- `docs/hitl_text_pack.yaml` — 18 запросов для прогона.
- `ingest/seeds/riga.yaml` — 19 seed-страниц Wikipedia.
- `src/rag/prompts/tagger.j2` — LLM-tagger промпт (транслит).
- `src/rag/nodes/text_search.py` — поиск place_id (Chroma + rapidfuzz).
- `scripts/run_hitl.py` — раннер HITL.
- `scripts/daily_rollup.py` — рапорт по логам JSONL (M2/M3/M5 метрики).
