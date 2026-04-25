# Riga Guide — задача для Antigravity (M10 Deploy)

**Контекст:** M8 + M9 закрыты. KB наполнена 18 местами (316 chunks), HITL прошёл с 14/16 точных совпадений в первом прогоне; после patch ingest ожидаем 16/16. Клод запускает повторный HITL и затем переходит к развёртыванию на VPS.

**Твоя зона:** инфраструктурная подготовка к deploy. Всё локально и без квоты Gemini API. Параллельно с Клодом, не блокирует.

---

## Контекст из последней сессии (что уже сделано Клодом)

- KB: 18 unique place_ids, 316 chunks. Все транслит. Артефакт patch ingest: `data/riga_patch_2026-04-25.yaml` (можно удалить или оставить для истории).
- `docker-compose.yml`: для сервиса `ingest` добавлены volumes `./logs`, `./docs:ro`, `./tests:ro` — теперь HITL можно запускать без `-v` костылей.
- `seeds/riga.yaml`: 3 названия исправлены: `Шведские ворота` (без скобок), `Дом с чёрными котами` (вместо «Кошкин дом»), убран `Югендстиль в Риге` (нет статьи на ru.wiki).
- `docs/hitl_text_pack.yaml`: expected_place_id обновлены под транслит и под фактические id из KB (включая `koshachij-dom-riga`).

---

## Задача 1 — Backup/restore скрипты для KB (P0)

**Цель:** на VPS должна быть возможность сделать бэкап KB одной командой и восстановить её.

**Файлы:**
- `scripts/backup_kb.sh` — bash-скрипт, делает `tar.gz` из `data/chroma/` и `data/bot.db` в `backups/kb_backup_YYYY-MM-DD_HHMMSS.tar.gz`. Удаляет бэкапы старше 14 дней (через `find -mtime`).
- `scripts/restore_kb.sh` — bash-скрипт, принимает path к tar.gz, аккуратно разворачивает в `data/`. Перед распаковкой делает safety-копию текущей `data/` в `data/.pre-restore-backup/`. Печатает что сделано.

**Тесты:**
- Запустить backup локально → проверить что файл создан, по объёму ~5-15 MB.
- Запустить restore локально → проверить что Chroma и bot.db на месте, count() в Chroma тот же.

**Куда положить:** `scripts/backup_kb.sh`, `scripts/restore_kb.sh`. Сделать `chmod +x` и упомянуть в `DEPLOY.md` §6 (обновление KB).

**НЕ делай:** не подключай rclone/s3/любые внешние хранилища. Это локальный tar.gz, остальное — оставим Натали.

---

## Задача 2 — systemd unit для VPS (P1)

**Цель:** на VPS бот должен автоматически перезапускаться при ребуте сервера и при падении.

**Файл:** `infra/systemd/riga-guide.service`

**Содержимое (template):**
```ini
[Unit]
Description=Riga Guide Telegram Bot
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/riga_guide
ExecStart=/usr/bin/docker compose up -d bot
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=120
Restart=on-failure
RestartSec=15s

[Install]
WantedBy=multi-user.target
```

**Также:**
- В `DEPLOY.md` §4 (или новой §7) добавить инструкцию установки:
  ```bash
  sudo cp infra/systemd/riga-guide.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now riga-guide
  systemctl status riga-guide  # проверка
  journalctl -u riga-guide -f  # логи
  ```

**НЕ делай:** не пытайся сам устанавливать unit (нет SSH-доступа). Только подготовить файл и инструкцию.

---

## Задача 3 — Cron для daily_rollup и backup (P1)

**Цель:** на VPS должны автоматически запускаться:
- `daily_rollup.py` — каждый день в 23:55 локального времени, складывать отчёт в `logs/rollup/YYYY-MM-DD.md`.
- `backup_kb.sh` — каждый день в 04:00, складывать в `backups/`.

**Файл:** `infra/cron/riga-guide.cron`

**Содержимое:**
```cron
# Riga Guide — automated tasks
55 23 * * * cd /opt/riga_guide && docker compose run --rm ingest python scripts/daily_rollup.py --out logs/rollup/$(date +\%Y-\%m-\%d).md >> logs/cron.log 2>&1
0 4 * * * cd /opt/riga_guide && bash scripts/backup_kb.sh >> logs/cron.log 2>&1
```

**Также:** в DEPLOY.md упомянуть, как установить:
```bash
sudo cp infra/cron/riga-guide.cron /etc/cron.d/riga-guide
sudo chmod 644 /etc/cron.d/riga-guide
```

**Заметки:**
- daily_rollup.py принимает аргумент `--out` (если нет — добавь, тривиальный fallback на stdout).
- Перед коммитом проверь, что `daily_rollup.py` не падает на пустых логах.

---

## Задача 4 — USER_GUIDE.md для гостей Натали (P2)

**Цель:** короткая документация (1-2 страницы) для гостей, которые будут пользоваться ботом.

**Файл:** `docs/USER_GUIDE.md`

**Структура:**
- Кто это и что умеет (1 абзац).
- Как начать — найти бота по @username, /start.
- 3 варианта запросов:
  1. Текст: «Дом Черноголовых» → бот расскажет.
  2. Фото: отправить фотографию места → бот узнает по картинке.
  3. Геолокация: отправить геопозицию → бот покажет 3 ближайших места.
- Примеры из реальной KB (опираться на список 18 мест из `data/bot.db`).
- Что бот НЕ умеет: бронирование, маршруты, погода, текущие цены.
- Контакт Натали для фидбэка (можно placeholder — Natalja подставит).

**На каком языке:** русский (целевая аудитория — русскоязычные гости).

**НЕ делай:** не делай скриншотов (нечего скринить пока бот не на VPS), не объясняй техническую архитектуру.

---

## Задача 5 — DISTANCE_STRICT эксперимент (P2, опционально)

**Цель:** разобраться, можно ли поднять `DISTANCE_STRICT` в `src/rag/nodes/text_search.py` с 0.30 до 0.20-0.25, чтобы убрать false positive на запросах вне KB. Сейчас «старые ворота» ложно матчилось в `tri-brata-riga` (после patch уже не воспроизводится, но это везение).

**Шаги:**
1. Прочитать `src/rag/nodes/text_search.py` — понять, как работает порог.
2. Найти существующие unit-тесты в `tests/` для text_search → запустить.
3. Поднять порог локально → пере-прогнать тесты → если не сломалось, оставить 0.25.
4. Если сломалось → откатить и описать в `work/m10-deploy/distance_strict_finding.md` что именно ломается. Не коммить изменение.

**НЕ делай:** не запускай HITL — это стоит квоту Gemini, проверяет Клод по своему графику.

---

## Что коммитить

Каждая задача — отдельный коммит:
- `feat(infra): KB backup/restore scripts`
- `feat(infra): systemd unit + cron for VPS`
- `docs: USER_GUIDE.md для гостей`
- (опционально) `chore(rag): подняты пороги text_search` или `docs: distance_strict findings`

Не делай монолитный «infra: M10 prep» коммит — Клоду будет сложно понять что к чему.

---

## Что НЕ делать

- **Не запускать HITL** — это квота Gemini.
- **Не пересобирать ingest полный** — это квота Gemini.
- **Не делать `docker system prune`** или другие deструктивные docker-команды.
- **Не редактировать код RAG-графа** (`src/rag/graph.py`, `src/rag/nodes/*` за исключением задачи 5) — там всё работает.
- **Не редактировать `seeds/riga.yaml`** — финализирован Клодом.

---

## Если будут вопросы

- `PROTOCOL.md` — журнал работы, последняя запись — 2026-04-25 «M8/M9 закрытие + patch».
- `IMPLEMENTATION_PLAN.md` (если есть) — общий план фаз M0..M12.
- `work/m10-deploy/next_session_claude.md` — параллельная задача Клода.

После выполнения — обнови `PROTOCOL.md` своей записью с маркером 🛠️ Antigravity.
