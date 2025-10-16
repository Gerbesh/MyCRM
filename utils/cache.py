"""Вспомогательные функции для кэширования ответов.

Позволяют использовать условные запросы через заголовки
ETag/If-None-Match и Last-Modified/If-Modified-Since.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from typing import Any, Sequence

from flask import Response, request


def prepare_cache(
    data: Sequence[Any], last_modified: datetime
) -> Response | tuple[str, str]:
    """Проверить условные заголовки и подготовить ETag/Last-Modified.

    Возвращает ``Response`` со статусом 304, если данные не изменились,
    либо кортеж ``(etag, last_modified_str)`` для установки заголовков.
    """
    if last_modified.tzinfo is None:
        last_modified = last_modified.replace(tzinfo=timezone.utc)
    last_modified = last_modified.replace(microsecond=0)

    etag_source = json.dumps(list(data), ensure_ascii=False, sort_keys=True).encode(
        "utf-8"
    )
    etag = hashlib.sha256(etag_source).hexdigest()
    last_modified_str = format_datetime(last_modified, usegmt=True)

    inm = request.headers.get("If-None-Match")
    if inm == etag:
        resp = Response(status=304)
        resp.headers["ETag"] = etag
        resp.headers["Last-Modified"] = last_modified_str
        return resp

    ims = request.headers.get("If-Modified-Since")
    if ims:
        try:
            ims_dt = parsedate_to_datetime(ims)
            if ims_dt >= last_modified:
                resp = Response(status=304)
                resp.headers["ETag"] = etag
                resp.headers["Last-Modified"] = last_modified_str
                return resp
        except (TypeError, ValueError):
            pass

    return etag, last_modified_str
