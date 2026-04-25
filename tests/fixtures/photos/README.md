# Тестовые фото для HITL прогона

Фото скачаны с Wikimedia Commons под свободными лицензиями (CC-BY / CC-BY-SA / Public Domain).
Размер каждого файла ≤ 500 KB (масштабированы через System.Drawing, JPEG 82-85%).

## Файлы и атрибуция

| Файл | Объект | Ожидаемый `place_id` | Автор | Лицензия | Источник |
|------|--------|----------------------|-------|----------|----------|
| `01_dome_cathedral.jpg` | Домский собор (снаружи) | `domskij-sobor-riga` | Ryzhkov Sergey | CC BY-SA 4.0 | [Wikimedia](https://commons.wikimedia.org/wiki/File:Riga_Dome_Cathedral_at_twilight.jpg) |
| `02_blackheads.jpg` | Дом Черноголовых | `dom-chernogolovykh` | Diliff | CC BY-SA 3.0 | [Wikimedia](https://commons.wikimedia.org/wiki/File:House_of_Blackheads_at_Dusk_1,_Riga,_Latvia_-_Diliff.jpg) |
| `03_freedom_monument.jpg` | Памятник Свободы | `pamyatnik-svobody-riga` | Iikka Kivi / Nimmari | Public Domain | [Wikimedia](https://commons.wikimedia.org/wiki/File:Freedom_Monument_Riga.jpg) |
| `04_riga_castle.jpg` | Рижский замок | `rizhskij-zamok-riga` | Sandis Spolītis | CC BY-SA 4.0 | [Wikimedia](https://commons.wikimedia.org/wiki/File:Riga_castle.jpg) |
| `05_unknown.jpg` | Спасская башня Кремля (не Латвия) | `not_recognized` ожидаем | Vyacheslav Argenberg | CC BY 2.0 | [Wikimedia](https://commons.wikimedia.org/wiki/File:Kremlin_Spasskaya_Tower-1.jpg) |

## Критерии качества (M2 из USER_SPEC)
- confidence ≥ 0.7 для объектов из KB (01–04)
- `not_recognized` для неизвестных мест (05) — **ок**
- Latency p50 < 8000ms, p95 < 15000ms

## Запуск с фото:
```bash
docker compose run --rm ingest python scripts/run_hitl.py \
  --photos-dir tests/fixtures/photos \
  --text-pack docs/hitl_text_pack.yaml \
  --out logs/hitl_2026-04-25.csv
```

## Примечание по лицензиям
- **CC BY-SA 3.0/4.0** — при распространении указывай автора и сохраняй лицензию.
- **CC BY 2.0** — при распространении указывай автора.
- **Public Domain** — свободное использование без ограничений.

