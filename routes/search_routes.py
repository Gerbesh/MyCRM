"""Маршруты для поиска и вспомогательные функции."""

from difflib import SequenceMatcher

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required
from jellyfish import levenshtein_distance, metaphone, soundex
from thefuzz import fuzz

from security_utils import sanitize_input
from utils.text_utils import similarity

search_bp = Blueprint("search", __name__)


def advanced_search_similarity(query, text, threshold=0.4):
    """
    Продвинутая функция поиска с несколькими алгоритмами сопоставления
    """
    if not query or not text:
        return 0

    query_lower = query.lower()
    text_lower = text.lower()

    # 1. Точное совпадение (максимальный вес)
    if query_lower in text_lower:
        return 1.0

    # 2. Fuzzy matching с разными алгоритмами
    # Ratio - простое сходство
    ratio_score = fuzz.ratio(query_lower, text_lower) / 100.0

    # Partial Ratio - для частичных совпадений
    partial_score = fuzz.partial_ratio(query_lower, text_lower) / 100.0

    # Token Sort Ratio - для перестановленных слов
    token_sort_score = fuzz.token_sort_ratio(query_lower, text_lower) / 100.0

    # Token Set Ratio - для наборов слов
    token_set_score = fuzz.token_set_ratio(query_lower, text_lower) / 100.0

    # 3. Фонетическое сопоставление
    try:
        query_soundex = soundex(query_lower)
        text_soundex = soundex(text_lower)
        phonetic_score = 1.0 if query_soundex == text_soundex else 0.0
    except Exception:
        phonetic_score = 0.0

    try:
        query_metaphone = metaphone(query_lower)
        text_metaphone = metaphone(text_lower)
        metaphone_score = 1.0 if query_metaphone == text_metaphone else 0.0
    except Exception:
        metaphone_score = 0.0

    # 4. Расстояние Левенштейна
    try:
        lev_distance = levenshtein_distance(query_lower, text_lower)
        max_len = max(len(query_lower), len(text_lower))
        lev_score = 1.0 - (lev_distance / max_len) if max_len > 0 else 0.0
    except Exception:
        lev_score = 0.0

    # 5. SequenceMatcher для базового сравнения
    sequence_score = SequenceMatcher(None, query_lower, text_lower).ratio()

    # Комбинированный счет с весами
    combined_score = (
        ratio_score * 0.25  # 25% - базовое нечеткое совпадение
        + partial_score * 0.3  # 30% - частичное совпадение (важно для поиска)
        + token_sort_score * 0.15  # 15% - сортировка токенов
        + token_set_score * 0.15  # 15% - набор токенов
        + phonetic_score * 0.1  # 10% - фонетическое совпадение
        + metaphone_score * 0.05  # 5% - метафон
        + lev_score * 0.05  # 5% - расстояние Левенштейна
        + sequence_score * 0.05  # 5% - последовательное сравнение
    )

    # Дополнительные бонусы для улучшения поиска
    # Бонус за совпадение в начале строки
    if text_lower.startswith(query_lower):
        combined_score += 0.1

    # Бонус за совпадение целых слов
    query_words = query_lower.split()
    text_words = text_lower.split()

    word_matches = sum(1 for q_word in query_words if q_word in text_words)
    if word_matches > 0:
        word_bonus = min(word_matches / len(query_words), 1.0) * 0.2
        combined_score += word_bonus

    # Ограничиваем максимальный счет
    combined_score = min(combined_score, 1.0)

    return combined_score if combined_score >= threshold else 0.0


def search_with_multiple_fields(query, items, fields, threshold=0.4):
    """
    Поиск по нескольким полям с продвинутым алгоритмом
    """
    results = []

    for item in items:
        max_score = 0
        best_field = None

        for field in fields:
            field_value = getattr(item, field, None)
            if field_value:
                score = advanced_search_similarity(query, str(field_value), threshold)
                if score > max_score:
                    max_score = score
                    best_field = field

        if max_score >= threshold:
            results.append((item, max_score, best_field))

    # Сортируем по релевантности
    results.sort(key=lambda x: x[1], reverse=True)

    return results


@search_bp.route("/search_objects")
@login_required
def search_objects():
    try:
        from models import Object

        query = request.args.get("query", "").strip()

        # Валидация и санитизация запроса
        query, valid, error = sanitize_input(query, max_length=100)
        if not valid:
            return jsonify({"error": error}), 400

        if len(query) < 2:
            return jsonify({"items": [], "has_next": False})

        page = request.args.get("page", 1, type=int)
        per_page = 10
        pagination = (
            Object.query.filter(Object.name.ilike(f"%{query}%"))
            .order_by(Object.name)
            .paginate(page=page, per_page=per_page, error_out=False)
        )

        items = [
            {"id": obj.id, "name": obj.name, "address": obj.address or ""}
            for obj in pagination.items
        ]
        return jsonify({"items": items, "has_next": pagination.has_next})
    except Exception as e:
        current_app.logger.error(f"Error in search_objects: {str(e)}")
        return jsonify({"error": "Ошибка поиска"}), 500


@search_bp.route("/search_contractors")
@login_required
def search_contractors():
    try:
        from models import Contractor

        query = request.args.get("query", "").strip()

        # Валидация и санитизация запроса
        query, valid, error = sanitize_input(query, max_length=100)
        if not valid:
            return jsonify({"error": error}), 400

        if len(query) < 2:
            return jsonify([])

        contractors = (
            Contractor.query.filter(Contractor.name.ilike(f"%{query}%")).limit(10).all()
        )

        return jsonify([{"id": c.id, "name": c.name} for c in contractors])
    except Exception as e:
        current_app.logger.error(f"Error in search_contractors: {str(e)}")
        return jsonify({"error": "Ошибка поиска"}), 500


@search_bp.route("/search")
@login_required
def search():
    """Общий поиск"""
    try:
        query = request.args.get("query", "").strip()
        search_type = request.args.get("type")
        if not query or not search_type:
            return jsonify({"items": [], "query": query})

        items = []
        if search_type == "object":
            from models import Object

            items = Object.query.all()
        elif search_type == "contractor":
            from models import Contractor

            items = Contractor.query.all()
        else:
            return jsonify({"items": [], "query": query})

        results = []
        for item in items:
            sim = similarity(query, item.name)
            if sim >= 0.6:  # 60% совпадение
                results.append({"id": item.id, "name": item.name, "similarity": sim})

        # Сортируем по степени схожести
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return jsonify({"items": results[:5], "query": query})
    except Exception as e:
        current_app.logger.error(f"Error in /search: {str(e)}")
        return jsonify({"items": [], "query": query}), 500
