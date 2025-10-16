"""Тесты для текстовых утилит."""

from utils.text_utils import similarity


def test_similarity_basic():
    """Проверяет корректность вычисления схожести строк."""
    assert similarity("Тест", "тест") == 1.0
    assert 0 < similarity("abc", "abd") < 1.0
