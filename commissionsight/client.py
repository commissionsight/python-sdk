"""A lightweight, zero-dependency Python client for the CommissionSight API.

Mirrors the surface area of the official TypeScript SDK (``@commissionsight/sdk``).
"""

from __future__ import annotations

import json as _json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urlencode
from uuid import uuid4

from .errors import ApiError

__all__ = ["CommissionSightClient", "Transport", "query"]

# A transport sends one request and returns ``(status_code, response_text)``. Inject
# a custom one (e.g. in tests, or to use ``requests``/``httpx``) via the constructor.
Transport = Callable[[str, str, Dict[str, str], Optional[bytes]], Tuple[int, str]]

# A file argument may be a path, raw bytes, a binary file object, or an explicit
# ``(filename, content)`` tuple.
FileInput = Union[str, "os.PathLike[str]", bytes, bytearray, Tuple[str, Any], Any]


def query(params: Dict[str, Optional[Union[str, int, float]]]) -> str:
    """Build a ``?a=1&b=2`` query string, skipping ``None`` and empty-string values."""
    entries = [(k, v) for k, v in params.items() if v is not None and v != ""]
    if not entries:
        return ""
    return "?" + urlencode([(k, str(v)) for k, v in entries])


def _bool(value: Optional[bool]) -> Optional[str]:
    """Map a truthy flag to the API's ``"true"`` (or ``None`` to omit it)."""
    return "true" if value else None


def _file_field(file: FileInput) -> Tuple[str, bytes]:
    """Normalize a file argument to ``(filename, content_bytes)``."""
    if isinstance(file, (bytes, bytearray)):
        return ("upload", bytes(file))
    if isinstance(file, tuple):
        name, content = file
        data = content.read() if hasattr(content, "read") else content
        return (str(name), bytes(data))
    if isinstance(file, (str, os.PathLike)):
        path = os.fspath(file)
        with open(path, "rb") as fh:
            return (os.path.basename(path), fh.read())
    if hasattr(file, "read"):
        name = getattr(file, "name", "upload")
        return (os.path.basename(str(name)), file.read())
    raise TypeError("file must be a path, bytes, a file object, or a (filename, content) tuple")


def _encode_multipart(fields: List[Tuple[str, Union[str, Tuple[str, bytes]]]]) -> Tuple[bytes, str]:
    """Encode ``multipart/form-data``. A field value that is a ``(filename, bytes)``
    tuple is sent as a file part; anything else is sent as a plain text part."""
    boundary = "----commissionsight" + uuid4().hex
    body = bytearray()
    for name, value in fields:
        body += f"--{boundary}\r\n".encode()
        if isinstance(value, tuple):
            filename, content = value
            body += (
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            ).encode()
            body += b"Content-Type: application/octet-stream\r\n\r\n"
            body += content
            body += b"\r\n"
        else:
            body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            body += str(value).encode()
            body += b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _urllib_transport(
    method: str, url: str, headers: Dict[str, str], body: Optional[bytes]
) -> Tuple[int, str]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310 - trusted base URL
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:  # 4xx/5xx — surface body to the caller
        return exc.code, exc.read().decode("utf-8")


class CommissionSightClient:
    """Typed client for the CommissionSight REST API.

    Args:
        base_url: e.g. ``https://api.commissionsight.com/v1`` (trailing slash optional).
        token: a per-account API token, sent as ``Authorization: Bearer <token>``.
            May also be set/rotated later via :meth:`set_token`.
        transport: optional custom transport (mainly for tests); defaults to ``urllib``.
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        transport: Optional[Transport] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._transport = transport or _urllib_transport
        self.admin = _AdminAPI(self)

    def set_token(self, token: Optional[str]) -> None:
        """Set or clear the bearer token used for subsequent requests."""
        self._token = token

    # --- internal request plumbing ---
    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        multipart: Optional[List[Tuple[str, Any]]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        raw: bool = False,
    ) -> Any:
        url = f"{self._base_url}{path}"
        headers: Dict[str, str] = {}
        if self._token:
            headers["authorization"] = f"Bearer {self._token}"
        body: Optional[bytes] = None
        if multipart is not None:
            body, content_type = _encode_multipart(multipart)
            headers["content-type"] = content_type
        elif json_body is not None:
            body = _json.dumps(json_body).encode("utf-8")
            headers["content-type"] = "application/json"
        if extra_headers:
            headers.update(extra_headers)

        status, text = self._transport(method, url, headers, body)
        if status < 200 or status >= 300:
            parsed: Any = None
            try:
                parsed = _json.loads(text) if text else None
            except ValueError:
                parsed = None
            message = (
                str(parsed["title"])
                if isinstance(parsed, dict) and "title" in parsed
                else f"HTTP {status}"
            )
            raise ApiError(status, message, parsed)
        if raw:
            return text
        return _json.loads(text) if text else None

    # --- carriers / configs ---
    def list_carriers(self, with_config: bool = False) -> Dict[str, Any]:
        return self._request("GET", f"/carriers{query({'withConfig': _bool(with_config)})}")

    def get_carrier(self, carrier_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/carriers/{carrier_id}")

    def list_configs(self, carrier_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/carriers/{carrier_id}/configs")

    def get_config_version(self, carrier_id: str, version: int) -> Any:
        return self._request("GET", f"/carriers/{carrier_id}/configs/{version}")

    def create_config(self, carrier_id: str, config: Any) -> Dict[str, Any]:
        """Create an account-scoped carrier config override."""
        return self._request("POST", f"/carriers/{carrier_id}/configs", json_body=config)

    def test_config(self, carrier_id: str, config: Any, file: FileInput) -> Dict[str, Any]:
        """Dry-run a config against a sample file (maps + previews, persists nothing)."""
        return self._request(
            "POST",
            f"/carriers/{carrier_id}/configs/test",
            multipart=[("config", _json.dumps(config)), ("file", _file_field(file))],
        )

    def infer_config(
        self, carrier_id: str, file: FileInput, sheet_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Infer a draft config from a sample file."""
        fields: List[Tuple[str, Any]] = [("file", _file_field(file))]
        if sheet_name:
            fields.append(("sheetName", sheet_name))
        return self._request("POST", f"/carriers/{carrier_id}/configs/infer", multipart=fields)

    # --- files ---
    def upload_file(
        self,
        file: FileInput,
        carrier_id: str,
        period_year: int,
        period_month: int,
        webhook_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        replace: bool = False,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload a commission statement; kicks off an asynchronous ingest job.

        Pass ``replace=True`` to atomically retract+re-ingest an existing carrier+period
        (otherwise a duplicate period returns ``409 period_exists``). ``workspace_id`` is
        required for multi-workspace accounts. ``idempotency_key`` makes retries safe.
        """
        fields: List[Tuple[str, Any]] = [
            ("file", _file_field(file)),
            ("carrierId", carrier_id),
            ("periodYear", str(period_year)),
            ("periodMonth", str(period_month)),
        ]
        if webhook_url:
            fields.append(("webhookUrl", webhook_url))
        if replace:
            fields.append(("replace", "true"))
        if workspace_id:
            fields.append(("workspaceId", workspace_id))
        headers = {"idempotency-key": idempotency_key} if idempotency_key else None
        return self._request("POST", "/files", multipart=fields, extra_headers=headers)

    def list_files(
        self,
        carrier_id: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._request(
            "GET", f"/files{query({'carrierId': carrier_id, 'limit': limit, 'cursor': cursor})}"
        )

    def get_file(self, file_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/files/{file_id}")

    def rescore_file(self, file_id: str) -> Dict[str, Any]:
        """Re-score a file's period without re-uploading (after an out-of-order upload)."""
        return self._request("POST", f"/files/{file_id}/rescore")

    def retract_file(self, file_id: str) -> Dict[str, Any]:
        """Retract (unapply) a file's carrier+period and re-score the following month."""
        return self._request("DELETE", f"/files/{file_id}")

    def purge_file(self, file_id: str) -> Dict[str, Any]:
        """Purge the raw statement bytes from object storage (results remain). Idempotent."""
        return self._request("POST", f"/files/{file_id}/purge")

    # --- jobs ---
    def list_jobs(
        self,
        status: Optional[str] = None,
        carrier_id: Optional[str] = None,
        period_year: Optional[int] = None,
        period_month: Optional[int] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/jobs{query({'status': status, 'carrierId': carrier_id, 'periodYear': period_year, 'periodMonth': period_month, 'limit': limit, 'offset': offset})}",
        )

    def get_job(self, job_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/jobs/{job_id}")

    def download_exceptions(self, job_id: str) -> str:
        """Download a job's exception file (rejected rows + errors) as CSV text."""
        return self._request("GET", f"/jobs/{job_id}/exceptions", raw=True)

    def get_job_results(
        self,
        job_id: str,
        status: Optional[str] = None,
        owed_only: bool = False,
        chargeback: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/jobs/{job_id}/results{query({'status': status, 'owedOnly': _bool(owed_only), 'chargeback': _bool(chargeback), 'limit': limit, 'offset': offset})}",
        )

    def get_job_deltas(
        self,
        job_id: str,
        member_ref_id: Optional[str] = None,
        change_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/jobs/{job_id}/deltas{query({'memberRefId': member_ref_id, 'changeType': change_type})}",
        )

    def retry_job(self, job_id: str) -> Dict[str, Any]:
        return self._request("POST", f"/jobs/{job_id}/retry")

    # --- members ---
    def list_members(
        self,
        carrier_id: Optional[str] = None,
        status: Optional[str] = None,
        period_year: Optional[int] = None,
        period_month: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/members{query({'carrierId': carrier_id, 'status': status, 'periodYear': period_year, 'periodMonth': period_month})}",
        )

    def get_member(self, member_ref_id: str) -> Any:
        return self._request("GET", f"/members/{member_ref_id}")

    def get_member_timeline(self, member_ref_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/members/{member_ref_id}/timeline")

    def get_member_journey(self, member_ref_id: str) -> Dict[str, Any]:
        """Full audit journey of a member: every period, source file, status + changes."""
        return self._request("GET", f"/members/{member_ref_id}/journey")

    def get_policy_journey(self, policy_ref_id: str) -> Dict[str, Any]:
        """Full audit journey of a single policy (member-scoped)."""
        return self._request("GET", f"/policies/{policy_ref_id}/journey")

    def get_member_last_seen(self, member_ref_id: str) -> Any:
        return self._request("GET", f"/members/{member_ref_id}/last-seen")

    # --- team ---
    def list_team(self) -> Dict[str, Any]:
        return self._request("GET", "/team")

    def invite_teammate(self, email: str) -> Dict[str, Any]:
        return self._request("POST", "/team/invites", json_body={"email": email})

    def remove_teammate(self, user_id: str) -> Any:
        return self._request("DELETE", f"/team/{user_id}")

    # --- audit ---
    def list_audit(
        self,
        action: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._request(
            "GET", f"/audit{query({'action': action, 'limit': limit, 'offset': offset})}"
        )

    # --- comparisons / reports ---
    def compare(
        self,
        from_period: str,
        to_period: str,
        carrier_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        granularity: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/comparisons{query({'from': from_period, 'to': to_period, 'carrierId': carrier_id, 'workspaceId': workspace_id, 'granularity': granularity})}",
        )

    def rollup(
        self,
        period: Optional[str] = None,
        carrier_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/reports/rollup{query({'period': period, 'carrierId': carrier_id, 'workspaceId': workspace_id})}",
        )

    def list_chargebacks(
        self,
        period: Optional[str] = None,
        carrier_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/chargebacks{query({'period': period, 'carrierId': carrier_id, 'workspaceId': workspace_id, 'limit': limit, 'offset': offset})}",
        )

    def attrition(
        self,
        period: str,
        carrier_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/reports/attrition{query({'period': period, 'carrierId': carrier_id, 'workspaceId': workspace_id})}",
        )

    def attrition_series(
        self,
        months: Optional[int] = None,
        carrier_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/reports/attrition-series{query({'months': months, 'carrierId': carrier_id, 'workspaceId': workspace_id})}",
        )

    def data_quality(
        self, period: Optional[str] = None, workspace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        return self._request(
            "GET", f"/reports/data-quality{query({'period': period, 'workspaceId': workspace_id})}"
        )

    # --- expected commission rates (the "owed" model inputs) ---
    def list_expected_rates(self, carrier_id: Optional[str] = None) -> Dict[str, Any]:
        return self._request("GET", f"/expected-rates{query({'carrierId': carrier_id})}")

    def upsert_expected_rate(
        self,
        carrier_id: str,
        rate_type: str,
        rate_value: float,
        plan_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upsert the contracted rate for a carrier (+ optional plan). ``rate_value`` is a
        fraction for ``percent_of_premium`` (0.2 = 20%); dollars for ``flat_per_member``."""
        return self._request(
            "POST",
            "/expected-rates",
            json_body={
                "carrierId": carrier_id,
                "planCode": plan_code,
                "rateType": rate_type,
                "rateValue": rate_value,
            },
        )

    def delete_expected_rate(self, rate_id: str) -> Any:
        return self._request("DELETE", f"/expected-rates/{rate_id}")

    # --- webhooks ---
    def list_webhooks(self) -> Dict[str, Any]:
        return self._request("GET", "/webhooks")

    def create_webhook(self, url: str, events: List[str]) -> Dict[str, Any]:
        """Subscribe to job events. The signing ``secret`` is returned ONCE on creation."""
        return self._request("POST", "/webhooks", json_body={"url": url, "events": events})

    def delete_webhook(self, webhook_id: str) -> Any:
        return self._request("DELETE", f"/webhooks/{webhook_id}")

    # --- session / service ---
    def me(self) -> Dict[str, Any]:
        """The account behind the current token."""
        return self._request("GET", "/me")

    def list_workspaces(self) -> Dict[str, Any]:
        """The account's workspaces (and whether multi-workspace is enabled)."""
        return self._request("GET", "/workspaces")

    def health(self) -> Dict[str, Any]:
        """Liveness probe (no auth required)."""
        return self._request("GET", "/health")

    # --- billing / profile ---
    def get_billing(self) -> Dict[str, Any]:
        return self._request("GET", "/billing")

    def update_billing(self, details: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PUT", "/billing", json_body=details)

    def billing_preview(self) -> Dict[str, Any]:
        return self._request("GET", "/billing/preview")

    def create_setup_intent(self) -> Dict[str, Any]:
        return self._request("POST", "/billing/setup-intent")

    def save_payment_method(self, payment_method_id: str) -> Dict[str, Any]:
        return self._request(
            "POST", "/billing/payment-method", json_body={"paymentMethodId": payment_method_id}
        )


class _AdminAPI:
    """Admin endpoints (require an ``admin``-role session). Accessed via ``client.admin``."""

    def __init__(self, client: CommissionSightClient) -> None:
        self._c = client

    def list_accounts(self, status: Optional[str] = None) -> Dict[str, Any]:
        return self._c._request("GET", f"/admin/accounts{query({'status': status})}")

    def set_billing_rate(self, account_id: str, rate_cents: Optional[int]) -> Dict[str, Any]:
        return self._c._request(
            "PUT", f"/admin/accounts/{account_id}/billing-rate", json_body={"rateCents": rate_cents}
        )

    def get_account_billing(self, account_id: str) -> Dict[str, Any]:
        return self._c._request("GET", f"/admin/accounts/{account_id}/billing")

    def account_overview(self, account_id: str) -> Dict[str, Any]:
        """Per-account dashboard: counts + latest-period rollup."""
        return self._c._request("GET", f"/admin/accounts/{account_id}/overview")

    def account_files(
        self, account_id: str, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> Dict[str, Any]:
        return self._c._request(
            "GET", f"/admin/accounts/{account_id}/files{query({'limit': limit, 'offset': offset})}"
        )

    def account_jobs(
        self, account_id: str, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> Dict[str, Any]:
        return self._c._request(
            "GET", f"/admin/accounts/{account_id}/jobs{query({'limit': limit, 'offset': offset})}"
        )

    def account_users(self, account_id: str) -> Dict[str, Any]:
        return self._c._request("GET", f"/admin/accounts/{account_id}/users")

    def cron_runs(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Recent scheduled-maintenance (cron) runs + the task schedule."""
        return self._c._request("GET", f"/admin/system/cron-runs{query({'limit': limit})}")

    def revenue(self) -> Dict[str, Any]:
        """Platform billing/revenue summary — heartbeats, projected revenue, A/R."""
        return self._c._request("GET", "/admin/revenue")

    def set_ai_settings(
        self,
        account_id: str,
        cap_cents: Optional[int] = None,
        passthrough: Optional[bool] = None,
    ) -> Dict[str, Any]:
        settings: Dict[str, Any] = {}
        if cap_cents is not None:
            settings["capCents"] = cap_cents
        if passthrough is not None:
            settings["passthrough"] = passthrough
        return self._c._request(
            "PUT", f"/admin/accounts/{account_id}/ai-settings", json_body=settings
        )

    def set_surcharge(self, account_id: str, enabled: bool) -> Dict[str, Any]:
        return self._c._request(
            "PUT", f"/admin/accounts/{account_id}/surcharge", json_body={"enabled": enabled}
        )

    def approve_account(self, account_id: str) -> Dict[str, Any]:
        return self._c._request("POST", f"/admin/accounts/{account_id}/approve")

    def provision_account(
        self, account_id: str, conn_string: Optional[str] = None
    ) -> Dict[str, Any]:
        """Provision (or re-provision) an account's data store. Pass ``conn_string`` to use
        a database created out of band; omit it to auto-create a Neon DB."""
        body = {"connString": conn_string} if conn_string else {}
        return self._c._request("POST", f"/admin/accounts/{account_id}/provision", json_body=body)

    def create_account(self, name: str) -> Dict[str, Any]:
        return self._c._request("POST", "/admin/accounts", json_body={"name": name})

    def purge_account_files(self, account_id: str) -> Dict[str, Any]:
        """Purge ALL raw statement bytes for an account from object storage."""
        return self._c._request("POST", f"/admin/accounts/{account_id}/purge-files")

    def issue_token(self, account_id: str, label: Optional[str] = None) -> Dict[str, Any]:
        return self._c._request(
            "POST", f"/admin/accounts/{account_id}/tokens", json_body={"label": label}
        )

    def list_tokens(self, account_id: str) -> Dict[str, Any]:
        """List an account's API tokens — metadata only (never the secret)."""
        return self._c._request("GET", f"/admin/accounts/{account_id}/tokens")

    def revoke_token(self, token_id: str) -> Dict[str, Any]:
        return self._c._request("POST", f"/admin/tokens/{token_id}/revoke")

    def store_credentials(
        self, account_id: str, conn_string: str, region: Optional[str] = None
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"connString": conn_string}
        if region:
            body["region"] = region
        return self._c._request(
            "PUT", f"/admin/accounts/{account_id}/credentials", json_body=body
        )

    def create_carrier(self, name: str, slug: str) -> Dict[str, Any]:
        return self._c._request("POST", "/admin/carriers", json_body={"name": name, "slug": slug})

    def rename_carrier(self, carrier_id: str, name: str, slug: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"name": name}
        if slug:
            body["slug"] = slug
        return self._c._request("PUT", f"/admin/carriers/{carrier_id}", json_body=body)

    def infer_config(
        self,
        carrier_id: str,
        file: FileInput,
        sheet_name: Optional[str] = None,
        file_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Onboarding: infer a draft config from a sample statement (CSV/XLSX)."""
        fields: List[Tuple[str, Any]] = [("file", _file_field(file))]
        if sheet_name:
            fields.append(("sheetName", sheet_name))
        if file_type:
            fields.append(("fileType", file_type))
        return self._c._request(
            "POST", f"/admin/carriers/{carrier_id}/configs/infer", multipart=fields
        )

    def list_users(self) -> Dict[str, Any]:
        return self._c._request("GET", "/admin/users")

    def create_user(
        self,
        email: str,
        account_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"email": email}
        if account_id:
            body["accountId"] = account_id
        if role:
            body["role"] = role
        return self._c._request("POST", "/admin/users", json_body=body)

    def update_user(self, user_id: str, role: str) -> Dict[str, Any]:
        """Update a user's role. A user's account link is immutable (set at invite)."""
        return self._c._request("PUT", f"/admin/users/{user_id}", json_body={"role": role})

    def delete_user(self, user_id: str) -> Dict[str, Any]:
        return self._c._request("DELETE", f"/admin/users/{user_id}")

    def create_global_config(self, carrier_id: str, config: Any) -> Dict[str, Any]:
        return self._c._request(
            "POST", f"/admin/carriers/{carrier_id}/configs", json_body=config
        )

    def list_carrier_configs(self, carrier_id: str) -> Dict[str, Any]:
        return self._c._request("GET", f"/admin/carriers/{carrier_id}/configs")

    def update_carrier_config(self, carrier_id: str, config_id: str, config: Any) -> Dict[str, Any]:
        return self._c._request(
            "PUT", f"/admin/carriers/{carrier_id}/configs/{config_id}", json_body=config
        )

    def add_allowlist(self, email: str) -> Dict[str, Any]:
        return self._c._request("POST", "/admin/allowlist", json_body={"email": email})

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._c._request(
            "GET", f"/admin/jobs{query({'status': status, 'limit': limit, 'offset': offset})}"
        )

    def job_detail(self, job_id: str) -> Dict[str, Any]:
        return self._c._request("GET", f"/admin/jobs/{job_id}")

    def retry_job(self, job_id: str) -> Dict[str, Any]:
        return self._c._request("POST", f"/admin/jobs/{job_id}/retry")

    def rescore_job(self, job_id: str) -> Dict[str, Any]:
        return self._c._request("POST", f"/admin/jobs/{job_id}/rescore")

    def metrics(self) -> Dict[str, Any]:
        return self._c._request("GET", "/admin/metrics")

    def logs(self, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        return self._c._request("GET", f"/admin/logs{query({'limit': limit, 'offset': offset})}")
