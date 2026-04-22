# Тестовые фото для HITL прогона

Положи сюда 3–5 реальных фото достопримечательностей Риги (jpg/png/webp).

## Рекомендуемые снимки для M9 HITL smoke:

| Файл                     | Объект                  | Ожидаемый place_id        |
|--------------------------|-------------------------|---------------------------|
| `01_dome_cathedral.jpg`  | Домский собор (снаружи) | `domskij-sobor-riga`      |
| `02_blackheads.jpg`      | Дом Черноголовых        | `dom-chernogolovjkh`      |
| `03_freedom_monument.jpg`| Памятник Свободы        | `pamyatnik-svobody`       |
| `04_riga_castle.jpg`     | Рижский замок           | `rizhskij-zamok`          |
| `05_unknown.jpg`         | Не-тестовое фото        | `not_recognized` ожидаем  |

## Критерии качества (M2 из USER_SPEC)
- Моделирование confidence ≥ 0.7 для объектов из KB
- Ошибка или not_recognized для неизвестных мест — **ок**
- Latency p50 < 8000ms, p95 < 15000ms

## Запуск с фото:
```bash
python scripts/run_hitl.py \
  --photos-dir tests/fixtures/photos \
  --text-pack docs/hitl_text_pack.yaml \
  --out hitl_results.csv
```
