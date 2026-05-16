# Задача для Antigravity — M14.1 Меню (ДОДЕЛАТЬ)

> **Назначение:** самодостаточный промпт для AG.
> **Статус:** в работе. AG уже сделал ~95% — осталось закоммитить и добавить тесты.
> **Обновлено:** 2026-05-16 Claude Code после обнаружения работы AG в working tree
> **Эстимейт:** 20-30 минут

---

## ⚠️ ВАЖНО: ситуация на старте

Когда я создавал эту задачу, я обнаружил что **ты уже сделал большую часть M14.1**, но не закоммитил. Файлы изменены в working tree:
- `src/bot/i18n_ru.py` — добавлены MENU_TITLE, 6 кнопок-констант, 3 примера, EVENTS_COMING_SOON_TMPL ✅
- `src/bot/ui.py` — добавлена `make_menu_keyboard()` (6 кнопок 2×3 + 3 примера в одной клавиатуре через `switch_inline_query_current_chat`) ✅
- `src/bot/gateway.py` — импорт `make_menu_keyboard`, хвост `on_start` с меню, отдельная команда `/menu`, callback-роутер `menu:*` с 6 заглушками ✅
- `src/bot/__main__.py` — регистрация хендлера `on_menu` для команды `/menu` ✅

Мы на ветке `m14-menu-categories-rating` ✅

**Что осталось:**
1. Юнит-тест на `make_menu_keyboard()`
2. Коммит всего сделанного
3. Локальный smoke-тест в Telegram

---

## Промпт для AG (копировать ниже)

---

Привет. Ты уже сделал почти всю M14.1 в проекте Riga Guide Bot, но не закоммитил. Сегодня надо дозакрыть.

**Контекст:** мы расширяем бота — добавляем меню «что я умею». План — `docs/M14_PLAN.md`, контракты — §4.1 и §4.2. Текущая ветка — `m14-menu-categories-rating`.

**Что уже сделано тобой (в working tree, не закоммичено):**
- `src/bot/i18n_ru.py` — добавлены константы меню (MENU_TITLE, MENU_BUTTON_*, MENU_EXAMPLE_*, EVENTS_COMING_SOON_TMPL)
- `src/bot/ui.py` — `make_menu_keyboard()` с 6 кнопками 2×3 + 3 примерами в одной клавиатуре
- `src/bot/gateway.py` — хвост `on_start` с меню, команда `/menu`, callback-роутер `menu:*` с 6 заглушками
- `src/bot/__main__.py` — регистрация `on_menu`

Проверь это командой: `git diff src/bot/`

---

## Что надо доделать

### Шаг 1 — Юнит-тест на клавиатуру меню

Расширь `tests/unit/test_ui.py` — добавь класс или функции для `make_menu_keyboard`:

```python
class TestMakeMenuKeyboard:
    def test_returns_inline_keyboard(self):
        from src.bot.ui import make_menu_keyboard
        from telegram import InlineKeyboardMarkup
        kb = make_menu_keyboard()
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_has_six_menu_buttons_and_three_examples(self):
        """6 категорий + 3 примера = 9 кнопок суммарно."""
        from src.bot.ui import make_menu_keyboard
        kb = make_menu_keyboard()
        # Раскладка: 3 ряда по 2 кнопки меню + 3 ряда по 1 кнопке-примеру = 6 рядов
        rows = kb.inline_keyboard
        assert len(rows) == 6, f"Expected 6 rows, got {len(rows)}"
        # Первые 3 ряда — по 2 кнопки (категории)
        for i in range(3):
            assert len(rows[i]) == 2, f"Row {i} should have 2 buttons"
        # Последние 3 ряда — по 1 кнопке (примеры)
        for i in range(3, 6):
            assert len(rows[i]) == 1, f"Row {i} should have 1 button"

    def test_menu_callback_data(self):
        """Категории имеют callback_data 'menu:<category>'."""
        from src.bot.ui import make_menu_keyboard
        kb = make_menu_keyboard()
        callbacks = []
        for row in kb.inline_keyboard[:3]:  # первые 3 ряда — категории
            for btn in row:
                callbacks.append(btn.callback_data)
        expected = {"menu:food", "menu:route", "menu:transport",
                    "menu:events", "menu:lifehack", "menu:top"}
        assert set(callbacks) == expected

    def test_examples_use_switch_inline_query(self):
        """Примеры используют switch_inline_query_current_chat, не callback_data."""
        from src.bot.ui import make_menu_keyboard
        kb = make_menu_keyboard()
        for row in kb.inline_keyboard[3:]:  # последние 3 ряда — примеры
            btn = row[0]
            assert btn.switch_inline_query_current_chat is not None
            assert btn.callback_data is None
```

Запусти: `docker compose run --rm bot pytest tests/unit/test_ui.py -v`

**Acceptance:** 4 новых теста зелёные, существующие тесты тоже не сломались.

---

### Шаг 2 — Локальный smoke-тест в Telegram

```bash
docker compose up bot
```

В Telegram своему боту:

1. `/start` → должен прийти welcome + второе сообщение с меню (6 кнопок категорий + 3 примера в одной клавиатуре).
2. `/menu` → должно прийти только меню (без welcome).
3. Тапни 🎭 «Что сейчас в городе» → должна прийти заглушка `EVENTS_COMING_SOON_TMPL`.
4. Тапни 🍴 «Где поесть» → должно прийти «Раздел 'Где поесть' в разработке...» (или текст заглушки).
5. Тапни пример «Как добраться из аэропорта?» → текст должен **подставиться в поле ввода**, НЕ отправиться автоматически.
6. Тапни остальные 4 категории — каждая отдаёт свою заглушку.

**Если что-то не работает** — поправь и коммить уже исправленную версию.

---

### Шаг 3 — Коммит

Стейджишь только файлы M14.1, без посторонних изменений:

```bash
git add src/bot/i18n_ru.py src/bot/ui.py src/bot/gateway.py src/bot/__main__.py tests/unit/test_ui.py
git status   # Проверка: только эти 5 файлов в Changes to be committed
git commit -m "feat(menu): inline menu + examples (M14.1)

- i18n_ru.py: MENU_TITLE, 6 кнопок-констант, 3 примера, EVENTS_COMING_SOON_TMPL
- ui.py: make_menu_keyboard() — 6 категорий 2x3 + 3 примера через switch_inline_query
- gateway.py: хвост on_start + команда /menu + callback-роутер menu:*
- __main__.py: регистрация on_menu
- test_ui.py: 4 теста на структуру клавиатуры

См. docs/M14_PLAN.md §4."
```

**НЕ пушь в master.** Ветка `m14-menu-categories-rating` остаётся локальной до approve Natalja.

---

### Шаг 4 — Запись в PROTOCOL

Добавь в `PROTOCOL.md` (после раздела «Текущий фокус», в самом верху журнала):

```markdown
### 2026-05-17 | M14.1 Меню 🛠️ Antigravity
**Исполнитель:** Antigravity
**Задачи:**
- [x] i18n_ru.py: 6 кнопок-констант + 3 примера + заглушка событий
- [x] ui.py: make_menu_keyboard() с 6 категориями 2×3 + 3 примерами в одной клавиатуре
- [x] gateway.py: хвост on_start, команда /menu, callback-роутер menu:* с 6 заглушками
- [x] __main__.py: регистрация on_menu
- [x] test_ui.py: 4 теста на структуру клавиатуры (зелёные)

**Результат:** меню работает локально, smoke-тест в Telegram прошёл.
**Решение по UX:** меню и примеры объединены в одну клавиатуру (вместо двух раздельных сообщений из §4.2 плана). Так удобнее пользователю — один экран, не надо скроллить.

**Handoff:** ветка `m14-menu-categories-rating`, коммит `<hash>`. Передаю Natalja на ревью UX в Telegram. После approve → мерж в master + деплой на VPS.
```

Закоммить и эту запись отдельным коммитом:
```bash
git add PROTOCOL.md
git commit -m "docs(protocol): M14.1 done by AG"
```

---

### Шаг 5 — Handoff Natalja

Скажи:
> M14.1 готов на ветке `m14-menu-categories-rating`, коммиты `<hash1>` (фича) и `<hash2>` (протокол). Юнит-тесты зелёные. Можно ревьюить UX в Telegram (`docker compose up bot` локально). Когда ок — мерж в master + деплой на VPS. После этого можно стартовать M14.2 (Транспорт + Лайфхаки) или M14.3 (Рейтинг) — на твой выбор.

---

## Известные расхождения с планом (не критичные)

1. **Одна клавиатура вместо двух:** в `M14_PLAN.md §4.2` было «второе сообщение с меню + третье с примерами». Ты объединил всё в одну клавиатуру. **Это лучше** — экономит экран. Зафиксируй это решение в записи PROTOCOL.

2. **Заглушки коротковаты:** «Раздел 'Где поесть' в разработке...» — функционально работает, но менее полезно, чем направление пользователя на свободный текст. Это **не блокер** — улучшим в M14.2/14.3/14.4/14.5, когда заменим заглушки реальной логикой.

3. **Префикс 💬 у примеров:** в ui.py ты добавил `f"💬 {i18n.MENU_EXAMPLE_1}"`. Это нормально — визуально отделяет «спроси меня» от категорий.

---

## Что важно

- **Файл `docs/M14_PLAN.md` не трогать** — это спека, не код.
- **Файлы в `work/m14/` не трогать** — это handoff-документы.
- **PROTOCOL.md уже редактировал Claude** — добавляй свою запись в начало журнала, не переписывай существующее.
- Если запутаешься — спроси Natalja, не делай по своему пониманию.
