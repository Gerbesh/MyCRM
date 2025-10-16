"""Утилиты для работы с текстом."""

from difflib import SequenceMatcher


def similarity(a: str, b: str) -> float:
    """Вычисляет схожесть двух строк (значение от 0 до 1)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()
