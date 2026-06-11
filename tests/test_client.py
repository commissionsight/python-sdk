"""Tests for the CommissionSight Python client.

Uses an injected fake transport (no network) — mirrors the TS SDK's mock-fetch tests.
"""

from __future__ import annotations

import json

import pytest

from commissionsight import ApiError, CommissionSightClient, query


def test_query_serializes_defined_params_and_skips_empties():
    assert query({"a": 1, "b": None, "c": "", "d": "x"}) == "?a=1&d=x"
    assert query({}) == ""


def _record_transport(status, body):
    """A transport that records the last request and returns a canned response."""
    calls = {}

    def transport(method, url, headers, data):
        calls["method"] = method
        calls["url"] = url
        calls["headers"] = headers
        calls["body"] = data
        return status, json.dumps(body)

    return transport, calls


def test_sends_bearer_token_and_parses_json():
    transport, calls = _record_transport(
        200, {"data": [{"id": "c1", "name": "Acme", "slug": "acme"}]}
    )
    client = CommissionSightClient("http://x/v1", token="tok", transport=transport)
    res = client.list_carriers()
    assert calls["headers"]["authorization"] == "Bearer tok"
    assert calls["url"] == "http://x/v1/carriers"
    assert res["data"][0]["slug"] == "acme"


def test_raises_api_error_with_problem_title_on_non_2xx():
    transport, _ = _record_transport(404, {"title": "Not found", "status": 404})
    client = CommissionSightClient("http://x/v1", transport=transport)
    with pytest.raises(ApiError) as exc:
        client.get_job("nope")
    assert exc.value.status == 404
    assert str(exc.value) == "Not found"
    assert exc.value.body == {"title": "Not found", "status": 404}


def test_base_url_trailing_slash_normalized():
    transport, calls = _record_transport(200, {"status": "ok"})
    client = CommissionSightClient("http://x/v1/", transport=transport)
    client.health()
    assert calls["url"] == "http://x/v1/health"


def test_set_token_rotates_and_clears():
    transport, calls = _record_transport(200, {"accountId": "a1"})
    client = CommissionSightClient("http://x/v1", transport=transport)
    client.me()
    assert "authorization" not in calls["headers"]
    client.set_token("new")
    client.me()
    assert calls["headers"]["authorization"] == "Bearer new"
    client.set_token(None)
    client.me()
    assert "authorization" not in calls["headers"]


def test_json_body_sets_content_type_and_serializes():
    transport, calls = _record_transport(200, {"status": "invited", "email": "a@b.com"})
    client = CommissionSightClient("http://x/v1", token="t", transport=transport)
    client.invite_teammate("a@b.com")
    assert calls["method"] == "POST"
    assert calls["headers"]["content-type"] == "application/json"
    assert json.loads(calls["body"]) == {"email": "a@b.com"}


def test_query_params_mapped_to_api_keys():
    transport, calls = _record_transport(200, {"data": []})
    client = CommissionSightClient("http://x/v1", transport=transport)
    client.get_job_results("job1", status="yellow", owed_only=True, limit=10)
    # snake_case kwargs map to the API's camelCase query keys; bools become "true".
    assert "/jobs/job1/results?" in calls["url"]
    assert "status=yellow" in calls["url"]
    assert "owedOnly=true" in calls["url"]
    assert "limit=10" in calls["url"]


def test_upload_file_sends_multipart_with_fields():
    transport, calls = _record_transport(
        200, {"jobId": "j1", "fileId": "f1", "status": "queued"}
    )
    client = CommissionSightClient("http://x/v1", token="t", transport=transport)
    res = client.upload_file(
        ("apr.csv", b"a,b,c\n1,2,3\n"),
        carrier_id="car_1",
        period_year=2026,
        period_month=4,
        idempotency_key="key-1",
    )
    assert res["jobId"] == "j1"
    assert calls["headers"]["content-type"].startswith("multipart/form-data; boundary=")
    assert calls["headers"]["idempotency-key"] == "key-1"
    body = calls["body"]
    assert b'name="carrierId"' in body and b"car_1" in body
    assert b'name="periodYear"' in body and b"2026" in body
    assert b'filename="apr.csv"' in body and b"a,b,c" in body


def test_admin_namespace_routes_under_admin():
    transport, calls = _record_transport(200, {"data": []})
    client = CommissionSightClient("http://x/v1", token="t", transport=transport)
    client.admin.list_accounts(status="pending")
    assert calls["url"] == "http://x/v1/admin/accounts?status=pending"


def test_raw_text_response_for_exception_download():
    def transport(method, url, headers, data):
        return 200, "member,error\nm1,bad rate\n"

    client = CommissionSightClient("http://x/v1", token="t", transport=transport)
    csv = client.download_exceptions("job1")
    assert csv == "member,error\nm1,bad rate\n"
