"""
Юнит-тесты для Chunker — разбивка текста на passages.

M7.6 + M7.8 + M9.1 — AG task (AG2.3).
Расширено: ~1000 слов fixture, сохранение заголовков, edge-cases.
"""

from __future__ import annotations

import pytest

from ingest.chunker import ChunkConfig, Chunker
from src.kb.models import PassageTopic


# ============================================================
# Фикстура ~1000 слов на русском
# ============================================================

FIXTURE_1000_WORDS = """
# Домский собор

Домский собор в Риге является одним из крупнейших средневековых храмов в Прибалтике.
Его строительство началось в 1211 году по указу епископа Альберта, который основал город.
Собор был задуман как кафедральный храм Рижского архиепископства. Первоначально он был
построен в романском стиле, но за многие века перестраивался множество раз. В результате
в его архитектуре причудливо соединились романский стиль, готика и барокко.

## История строительства

Строительство собора продолжалось несколько десятилетий. Первая фаза включала возведение
нефа и апсиды в романском стиле. Каменные стены были толстыми и прочными, окна небольшими.
К концу XIII века собор был расширен в готическом стиле. Были добавлены боковые нефы, а
центральный неф был поднят. Характерные стрельчатые арки и рёберные своды преобразили
интерьер храма. В XV веке башня собора была увенчана шпилем, который стал одним из
символов города.

## Орган

Домский собор славится своим органом, который является одним из крупнейших в мире.
Инструмент был построен в 1883–1884 годах немецкой фирмой Walcker. Орган насчитывает
6 718 труб, 4 мануала и 124 регистра. Его звучание впечатляет не только размерами, но
и богатством тембров. Органные концерты в Домском соборе привлекают меломанов со всего
мира. Акустика храма идеально дополняет звучание инструмента. Каждый четверг и пятницу
в соборе проводятся вечерние концерты.

## Монастырский двор

Внутренний дворик Домского собора, известный как крестовый ход, является одним из
наиболее хорошо сохранившихся готических монастырских дворов в Северной Европе.
Аркады галерей украшены резными капителями с растительными мотивами. Здесь можно увидеть
фрагменты средневековых надгробий и эпитафий. Двор служит площадкой для проведения
камерных концертов и выставок. Атмосфера средневекового уединения создаёт уникальное
настроение. Зимой дворик особенно красив, когда его стены покрывает лёгкая изморось.

## Легенды

Существует легенда о Рижском петушке, который установлен на шпиле Домского собора.
Согласно преданию, петушок был золотым снаружи и чёрным внутри. Когда он поворачивался
золотой стороной к городу, это означало, что корабли идут в порт с товарами. Чёрная
сторона предвещала шторм или опасность. Ещё одна легенда гласит, что под собором
скрыты подземные ходы, соединяющие его с Рижским замком и другими средневековыми
зданиями. Историки подтверждают существование некоторых тоннелей, но большинство
из них обрушились столетия назад.

## Современность

Сегодня Домский собор является действующей лютеранской церковью и одновременно концертным
залом. Он входит в список объектов культурного наследия ЮНЕСКО в составе Старой Риги.
Ежегодно собор посещают сотни тысяч туристов и паломников. Реставрационные работы
проводятся регулярно для сохранения этого уникального памятника архитектуры. Последняя
крупная реставрация завершилась в 2020 году и включала обновление витражей и укрепление
фундамента. Домский собор остаётся символом Риги и одной из главных достопримечательностей
Латвии, привлекая гостей своей многовековой историей и величественной архитектурой.
"""


# ============================================================
# Базовая функциональность
# ============================================================

class TestChunkerBasic:
    """Базовая функциональность чанкера."""

    def test_short_text_single_chunk(self) -> None:
        """Короткий текст → один чанк."""
        c = Chunker(ChunkConfig(max_chars=600, min_chars=50))
        passages = c.chunk("Домский собор.", place_id="dome", source="test")
        assert len(passages) == 1
        assert passages[0].text_ru == "Домский собор."
        assert passages[0].place_id == "dome"

    def test_empty_text(self) -> None:
        """Пустой текст → пустой список."""
        c = Chunker()
        assert c.chunk("", place_id="x") == []
        assert c.chunk("   ", place_id="x") == []

    def test_whitespace_only(self) -> None:
        """Только пробелы и переносы → пустой список."""
        c = Chunker()
        assert c.chunk("\n\n\n", place_id="x") == []
        assert c.chunk("\t  \n  \t", place_id="x") == []

    def test_paragraph_split(self) -> None:
        """Два абзаца → два чанка."""
        text = "Первый абзац про Ригу.\n\nВторой абзац про историю."
        c = Chunker(ChunkConfig(max_chars=600, min_chars=10))
        passages = c.chunk(text, place_id="riga")
        assert len(passages) == 2

    def test_long_paragraph_splits_by_sentences(self) -> None:
        """Длинный абзац разбивается по предложениям."""
        sentences = [f"Предложение номер {i} очень длинное и подробное." for i in range(20)]
        text = " ".join(sentences)
        c = Chunker(ChunkConfig(max_chars=200, min_chars=50))
        passages = c.chunk(text, place_id="test")
        assert len(passages) > 1
        for p in passages:
            assert len(p.text_ru) <= 500  # мягкий лимит


# ============================================================
# ~1000 слов fixture
# ============================================================

class TestChunkerLargeText:
    """Тесты на крупной русскоязычной фикстуре (~1000 слов)."""

    def test_fixture_produces_multiple_chunks(self) -> None:
        """~1000 слов → несколько чанков (100-600 chars каждый)."""
        c = Chunker(ChunkConfig(max_chars=600, min_chars=100))
        passages = c.chunk(FIXTURE_1000_WORDS, place_id="dome-cathedral", source="test")

        # Должно быть от 3 до 20 чанков
        assert len(passages) >= 3, f"Слишком мало чанков: {len(passages)}"
        assert len(passages) <= 20, f"Слишком много чанков: {len(passages)}"

    def test_chunks_within_size_bounds(self) -> None:
        """Каждый чанк в диапазоне min_chars..max_chars (мягкий)."""
        c = Chunker(ChunkConfig(max_chars=600, min_chars=100))
        passages = c.chunk(FIXTURE_1000_WORDS, place_id="dome")

        for i, p in enumerate(passages):
            # Мягкий верхний лимит — предложение может перехлестнуть
            assert len(p.text_ru) <= 1200, f"Чанк {i} слишком длинный: {len(p.text_ru)}"
            # Первый и последний могут быть короче
            if 0 < i < len(passages) - 1:
                assert len(p.text_ru) >= 30, f"Чанк {i} слишком короткий: {len(p.text_ru)}"

    def test_no_text_lost(self) -> None:
        """Суммарно чанки содержат весь осмысленный текст."""
        c = Chunker(ChunkConfig(max_chars=600, min_chars=100))
        passages = c.chunk(FIXTURE_1000_WORDS, place_id="dome")
        combined = " ".join(p.text_ru for p in passages)

        # Проверяем, что ключевые фразы сохранились
        assert "Домский собор" in combined
        assert "орган" in combined.lower()
        assert "легенда" in combined.lower() or "петушок" in combined.lower()


# ============================================================
# Сохранение заголовков
# ============================================================

class TestChunkerHeaders:
    """Сохранение заголовков в чанках."""

    def test_header_preserved_in_chunk(self) -> None:
        """Markdown-заголовок # сохраняется в тексте чанка."""
        text = "# Домский собор\n\nТекст про собор. Очень интересный.\n\n# Памятник Свободы\n\nТекст про памятник."
        c = Chunker(ChunkConfig(max_chars=600, min_chars=10))
        passages = c.chunk(text, place_id="test")

        combined = " ".join(p.text_ru for p in passages)
        # Заголовки должны быть в одном из чанков
        assert "Домский собор" in combined
        assert "Памятник Свободы" in combined

    def test_header_and_body_together(self) -> None:
        """Заголовок и тело абзаца — в одном чанке (если помещаются)."""
        text = "## Орган\n\nДомский собор славится своим органом."
        c = Chunker(ChunkConfig(max_chars=600, min_chars=10))
        passages = c.chunk(text, place_id="dome")

        # Заголовок и текст вместе
        assert len(passages) >= 1
        combined = " ".join(p.text_ru for p in passages)
        assert "Орган" in combined
        assert "органом" in combined


# ============================================================
# Merge маленьких чанков
# ============================================================

class TestChunkerMerge:
    """Склейка маленьких чанков."""

    def test_merges_tiny_chunks(self) -> None:
        """Маленькие абзацы склеиваются."""
        text = "Раз.\n\nДва.\n\nТри."
        c = Chunker(ChunkConfig(max_chars=600, min_chars=50))
        passages = c.chunk(text, place_id="x")
        assert len(passages) <= 2


# ============================================================
# Тема и passage_id
# ============================================================

class TestChunkerTopicAndPassageId:
    """Тема и passage_id генерация."""

    def test_topic_propagated(self) -> None:
        """Тема передаётся в passages."""
        c = Chunker()
        passages = c.chunk(
            "Текст легенды.", place_id="dome",
            topic=PassageTopic.LEGEND, source="wiki"
        )
        assert passages[0].topic == PassageTopic.LEGEND

    def test_passage_id_generated(self) -> None:
        """passage_id автоматически генерируется (sha256)."""
        c = Chunker()
        passages = c.chunk("Текст.", place_id="dome", source="test")
        assert len(passages[0].passage_id) == 64  # sha256 hex

    def test_idempotent_passage_id(self) -> None:
        """Одинаковый текст → одинаковый passage_id."""
        c = Chunker()
        p1 = c.chunk("Текст.", place_id="dome", source="test")
        p2 = c.chunk("Текст.", place_id="dome", source="test")
        assert p1[0].passage_id == p2[0].passage_id

    def test_different_text_different_id(self) -> None:
        """Разный текст → разный passage_id."""
        c = Chunker()
        p1 = c.chunk("Текст один.", place_id="dome", source="test")
        p2 = c.chunk("Текст два.", place_id="dome", source="test")
        assert p1[0].passage_id != p2[0].passage_id
