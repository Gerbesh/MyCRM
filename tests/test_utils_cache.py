import json
from datetime import datetime

import pytest

from utils.cache import prepare_cache


@pytest.fixture()
def cache_payload():
    return [
        {"id": 1, "name": "А"},
        {"id": 2, "name": "Б"},
    ]


def _expected_etag(data):
    return (
        __import__("hashlib")
        .sha256(
            json.dumps(list(data), ensure_ascii=False, sort_keys=True).encode("utf-8")
        )
        .hexdigest()
    )


def test_prepare_cache_generates_headers(app, cache_payload):
    naive_dt = datetime(2024, 1, 1, 12, 0, 0, 123456)
    with app.test_request_context():
        etag, last_modified = prepare_cache(cache_payload, naive_dt)

    assert etag == _expected_etag(cache_payload)
    assert last_modified.endswith("GMT")
    assert "," in last_modified  # формат RFC 7231


def test_prepare_cache_returns_304_for_matching_etag(app, cache_payload):
    etag = _expected_etag(cache_payload)
    last_modified = datetime(2024, 1, 2, 0, 0, 0)

    headers = {"If-None-Match": etag}
    with app.test_request_context(headers=headers):
        resp = prepare_cache(cache_payload, last_modified)

    assert resp.status_code == 304
    assert resp.headers["ETag"] == etag


def test_prepare_cache_uses_if_modified_since(app, cache_payload):
    last_modified = datetime(2024, 1, 3, 15, 0, 0)
    etag = _expected_etag(cache_payload)
    ims = last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")

    headers = {"If-Modified-Since": ims}
    with app.test_request_context(headers=headers):
        resp = prepare_cache(cache_payload, last_modified)

    assert resp.status_code == 304
    assert resp.headers["ETag"] == etag
    assert resp.headers["Last-Modified"].endswith("GMT")


def test_prepare_cache_ignores_invalid_if_modified_since(app, cache_payload):
    last_modified = datetime(2024, 1, 4, 12, 0, 0)

    headers = {"If-Modified-Since": "not-a-date"}
    with app.test_request_context(headers=headers):
        etag, last_modified_str = prepare_cache(cache_payload, last_modified)

    assert etag == _expected_etag(cache_payload)
    assert last_modified_str.endswith("GMT")
