# Riga Guide — точка входа для нового чата Claude (M10 DEPLOY)

**Дата:** 2026-04-25 (продолжение).
**Фаза:** M8 + M9 закрыты (зелёные с оговорками) → **M10 Deploy**.
**Цель сессии:** перезапустить HITL после patch ingest, зафиксировать 100% точность по KB, перейти к продакшен-деплою на VPS.

---

## 0. Что закрыто в предыдущей сессии (2026-04-25)

**Коммиты в master (порядок):**
- `1e79f2d` миграция google-genai SDK + транслит tagger + HITL pack 18 запросов
- `d3a6211` fix wikipedia disambig recursion (auto_suggest=False)
- `a2a468f` Dockerfile pip upgrade + «Памятник Свободы (Рига)»
- `eea2aa2` mute httpx/httpcore/google_genai loggers до WARNING
- `4d40763` PROTOCOL + handoff plans for new chat
- `228bd5a` (AG) DEPLOY.md + smoke photos
- `55639aa` (AG) PROTOCOL запись AG
- `8a09813` expected_place_id под факт KB
- *(новый)* docker-compose volumes + seed fixes + patch ingest + PROTOCOL

**KB:** Chroma 'places_ru', ожидаемо **18 place_id**, ~325 chunks (16 + 2 patch). Все транслит.

**HITL прогон 2026-04-25 (до patch):**
- 22/23 ok (5 фото + 18 текстов, 1 ожидаемый not_recognized)
- 14/16 текстов с однозначным expected_place_id — точные совпадения
- 4/4 фото с expected — точные
- 2 false positive связаны с упавшими 3 seeds (Шведские ворота, Кошкин дом, Югендстиль) → 2 из 3 пофиксили patch-ом

**Файлы прогона (для сверки):**
- `logs/hitl_2026-04-25.csv` — CSV старого прогона
- `logs/hitl_2026-04-25.stdout.log` — stdout с детальными логами

---

## 1. Первое действие — sanity check KB (быстро)

```bash
docker compose run --rm ingest python -c "
import chromadb
from collections import Counter
client = chromadb.PersistentClient(path='/app/data/chroma')
col = client.get_collection('places_ru')
print('Count:', col.count())
metas = (col.get(include=['metadatas'])['metadatas']) or []
ids = Counter(m.get('place_id', '?') for m in metas)
print(f'Unique place_ids: {len(ids)}')
for pid, n in sorted(ids.items(), key=lambda x: -x[1]):
    print(f'  {pid}: {n}')
"
```

Ожидаем (зафиксировано на конец 2026-04-25):
- **18 unique place_ids**, **316 chunks**
- В списке должны быть `shvedskie-vorota-riga` (6 passages) и `koshachij-dom-riga` (11 passages)

Если расходится — что-то поменялось, разбираться.

YAML `docs/hitl_text_pack.yaml` уже синхронизирован под эти id (Кошкин дом → koshachij-dom-riga).

---

## 2. Перезапустить HITL

```bash
docker compose run --rm ingest python scripts/run_hitl.py \
  --photos-dir tests/fixtures/photos \
  --text-pack docs/hitl_text_pack.yaml \
  --out logs/hitl_2026-04-25_v2.csv
```

**Ожидание:**
- 23/23 ok (или 22/23 если Спасская башня всё ещё not_recognized, что ок)
- 16/16 точных совпадений по expected_place_id среди текстов
- 5/5 фото
- avg_latency остаётся ~19s (ничего не оптимизировали)

---

## 3. Закрыть M8/M9 в PROTOCOL и переключиться на M10

```markdown
### 2026-04-?? | M8/M9 закрыто 🤖 Claude Code
- HITL v2: <X>/23 ok, <Y>/16 точных по expected_place_id
- 18 place_id в KB, 3 потерянных seed-а закрыты:
  - Шведские ворота (без скобок)
  - Дом с чёрными котами (вместо Кошкин дом)
  - Югендстиль в Риге — убран (нет статьи на ru.wiki)
- Остался известный issue: avg_latency 19s (бэклог M11)
**Текущий фокус:** M10 — deploy на VPS.
```

---

## 4. M10 — Deploy на VPS

### Чтение перед действиями
- `DEPLOY.md` (обновлён AG для google-genai) — пошаговая инструкция.
- `docker-compose.yml` — текущая конфигурация (volumes для bot/ingest).
- `Dockerfile` — multi-stage, python:3.12-slim.

### Обязательное: проверить наличие VPS
**Спроси Natalja**, есть ли доступ к VPS и какой провайдер. Если нет — задача отменяется до приобретения.

### Шаги deploy (требуют доступа к VPS)
1. SSH-ключ + git clone проекта на VPS.
2. `.env` на VPS (GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TAVILY_API_KEY).
3. Перенос KB (data/chroma/, data/bot.db) — через scp или volume backup.
4. `docker compose up -d bot` на VPS.
5. Telegram smoke-test через прод-бота: «Дом Черноголовых», «Рижский замок», фото Домского собора.
6. systemd unit для автозапуска docker compose (если нужно).

### Smoke-чеклист (из DEPLOY.md §5)
- [SDK] ingest 1 место без ошибок (см. AG-обновление DEPLOY.md)
- [BOT] /start отвечает
- [RAG] текст «Дом Черноголовых» — корректный place_id, story 7-8 предложений
- [VISION] фото 01_dome_cathedral.jpg — confidence ≥ 0.7

---

## 5. Бэклог (если есть время)

После успешного deploy — можно взять одно из:

1. **DISTANCE_STRICT поднять с 0.30 до 0.20-0.25**
   - Файл: `src/rag/nodes/text_search.py`
   - Тест: добавить unit-test с запросами вне KB → ожидаем `not_recognized` или `candidates`
   - Прогнать HITL — убедиться что точность по нормальным запросам не упала.

2. **Latency optimization (M11)**
   - Halluck_check на Haiku 4.5 (вместо Gemini Flash)
   - Embedding cache в Chroma sqlite для повторных query
   - Async параллелизация web_search + embed для ускорения cold paths

3. **Бэкап скрипты** (M12 / Maintain)
   - `scripts/backup_kb.sh` — tar.gz Chroma + bot.db в /backups
   - cron daily на VPS

---

## 6. Известные риски

- **Pipeline берёт первый place_id из чанков** — на обзорной странице «Рига» (96 passages) tagger разбросал по разным id, итоговый — `riga`. Это нормально, не блокер. Тематические запросы получают `staryj-gorod-riga` через retrieve-by-text.
- **DISTANCE_STRICT=0.30 даёт false positive** на запросах вне KB. После patch (добавили 2 места) ситуация лучше, но вне KB остаются: Эссенция, Лиепая, Юрмала и т.д. → semantic_strict может матчить близкое. Альтернативно — fallback в web_search при low-confidence.
- **VPS deploy без локального тестирования docker compose** — обязательно сначала прогнать `docker compose up bot` локально и smoke-тест в Telegram через текущий @riga_guide_bot (если токен боевой).

---

## 7. Полезные команды

```bash
# Статус Chroma
docker compose run --rm ingest python -c "import chromadb; c = chromadb.PersistentClient(path='/app/data/chroma').get_collection('places_ru'); print(c.count())"

# Список place_id в bot.db (только geo)
docker compose run --rm ingest python -c "import sqlite3; rows = sqlite3.connect('/app/data/bot.db').execute('SELECT place_id, name_ru FROM place_coords ORDER BY place_id').fetchall(); [print(r) for r in rows]"

# Запуск бота локально для smoke-теста
docker compose up bot
docker compose logs -f bot

# Daily rollup за сегодня
docker compose run --rm ingest python scripts/daily_rollup.py --date 2026-04-25
```

---

## 8. Ссылки

- `PROTOCOL.md` — журнал.
- `work/m10-deploy/ag-task-next.md` — параллельная задача для AG (M10).
- `DEPLOY.md` — пошаговый деплой (AG-обновлён).
- `docker-compose.yml` — теперь с volumes `./docs:/app/docs:ro`, `./tests:/app/tests:ro`, `./logs:/app/logs` для ingest.
- `data/riga_patch_2026-04-25.yaml` — patch-yaml использован для добивки KB. Можно удалить после M10.
