# commissionsight (Python)

[![PyPI](https://img.shields.io/pypi/v/commissionsight.svg)](https://pypi.org/project/commissionsight/)
[![license](https://img.shields.io/pypi/l/commissionsight.svg)](./LICENSE)

A lightweight, **zero-dependency** Python client for the [CommissionSight](https://commissionsight.com) API. It mirrors the surface area of the official [TypeScript SDK](https://github.com/commissionsight/sdk).

CommissionSight ingests carrier commission statements (CSV/XLSX), normalizes them across carriers, and scores every member period-over-period as **🟢 green / 🟡 yellow / 🔴 red** with explicit change flags — so you can see new business, commission changes, and attrition at a glance.

- **Zero runtime dependencies** — just the Python standard library (`urllib`).
- **Typed** — response shapes are exported as `TypedDict`s; the package ships `py.typed`.
- **Testable** — inject a custom transport (or your own `requests`/`httpx`) for tests and non-standard runtimes.
- **Python 3.8+**.

---

## Installation

```bash
pip install commissionsight
```

---

## Quick start

```python
from commissionsight import CommissionSightClient

cs = CommissionSightClient(
    "https://api.commissionsight.com/v1",
    token="...",  # a per-account API token
)

carriers = cs.list_carriers()
print(carriers["data"])  # [{"id": ..., "name": ..., "slug": ...}, ...]
```

### Client options

```python
CommissionSightClient(
    base_url,            # e.g. https://api.commissionsight.com/v1 (trailing slash optional)
    token=None,          # Bearer token; can also be set later via set_token()
    transport=None,      # custom transport (method, url, headers, body) -> (status, text)
)
```

Set or rotate the token at any time:

```python
cs.set_token(new_token)
cs.set_token(None)  # clear it
```

---

## Authentication

The SDK is for **server-to-server integrations**, authenticated with a **per-account API token** issued to you by CommissionSight. Every request is sent as `Authorization: Bearer <token>`.

---

## Uploading a statement & tracking the job

Uploading a file kicks off an asynchronous ingest **job**. Poll the job until it's `completed`, then read the scored results.

```python
import time

# `file` can be a path, bytes, a file object, or a (filename, content) tuple.
res = cs.upload_file(
    "statements/aetna-2026-05.csv",
    carrier_id="car_123",
    period_year=2026,
    period_month=5,
    webhook_url="https://acme.com/hooks/commissionsight",  # optional
    idempotency_key="acme-2026-05-aetna",                  # optional, safe retries
)
job_id = res["jobId"]

job = cs.get_job(job_id)
while job["status"] in ("queued", "processing"):
    time.sleep(1.5)
    job = cs.get_job(job_id)
if job["status"] == "failed":
    raise RuntimeError(job.get("error") or "ingest failed")

results = cs.get_job_results(job_id, status="yellow")
for row in results["data"]:
    print(row["memberRefId"], row["status"], row["flags"], row["commissionAmount"])
```

### Re-scoring after an out-of-order upload

If you upload an earlier month *after* a later one, the later period's scoring becomes stale. `list_files()` flags this with `rescoreSuggested`; refresh it without re-uploading:

```python
files = cs.list_files(carrier_id="car_123")
for f in files["data"]:
    if f.get("rescoreSuggested"):
        cs.rescore_file(f["id"])
```

### Correcting or removing a statement

Uploading over a carrier+period that already has a file fails with `409` (`period_exists`). To apply a **corrected file**, pass `replace=True`: the existing data is retracted and the corrected file re-ingested atomically. The following month is re-scored automatically.

```python
res = cs.upload_file(
    corrected_file,
    carrier_id="car_123",
    period_year=2026,
    period_month=4,
    replace=True,  # omit -> 409 period_exists if the period already exists
)
# res["mode"] == "replace"

# Or remove a period entirely (no re-upload), re-scoring the next month:
cs.retract_file(file_id)
```

---

## Status & flags

| `status`  | Meaning |
| --------- | ------- |
| 🟢 `green`  | Present and unchanged vs. the prior period. |
| 🟡 `yellow` | Present but something tracked changed (see flags). |
| 🔴 `red`    | Present in the prior period, **absent now** (dropped). |

| `flag`                    | Meaning |
| ------------------------- | ------- |
| `NEW`                     | First time this member is seen. |
| `COMMISSION_CHANGED`      | Commission amount differs from the prior period. |
| `DATA_CHANGED`            | A tracked non-commission field changed. |
| `DROPPED`                 | Was present before, missing now. |
| `REAPPEARED`              | Returned after being absent. |
| `REAPPEARED_WITH_DELTA`   | Returned **and** came back with a different commission. |
| `CHARGEBACK`              | A negative-commission (clawback) record this period. |

```python
from commissionsight import Status, Flag, ResultRow
```

---

## Reading data

```python
# Files & jobs
cs.list_files(carrier_id=carrier_id, limit=50)
cs.list_jobs(status="completed")
cs.get_job_results(job_id, status="red", limit=100, offset=0)
cs.get_job_deltas(job_id, change_type="COMMISSION_CHANGED")
cs.retry_job(job_id)

# Members & policies — status, timeline, and the full audit journey
cs.list_members(carrier_id=carrier_id, status="yellow")
cs.get_member_timeline(member_ref_id)
cs.get_member_journey(member_ref_id)   # every period, source file, status + field changes
cs.get_policy_journey(policy_ref_id)

# Rejected rows from an ingest (exception file, as CSV text)
csv_text = cs.download_exceptions(job_id)

# Carriers & their mapping configs
cs.list_carriers(with_config=True)
cs.list_configs(carrier_id)
```

### Commission owed (expected vs. actual)

```python
cs.upsert_expected_rate(carrier_id=carrier_id, rate_type="percent_of_premium", rate_value=0.2)
rollup = cs.rollup("2026-05", carrier_id)
print(rollup["totals"]["commissionOwed"], rollup["totals"]["owedEvaluated"])
```

### Chargebacks

```python
cb = cs.list_chargebacks(carrier_id=carrier_id)  # negative-commission events + original payout
```

### Webhooks

```python
cs.create_webhook(url="https://acme.com/hooks/cs", events=["job.completed"])
```

### Compare any two periods

```python
cmp = cs.compare(from_period="2026-04", to_period="2026-05", carrier_id=carrier_id)
print(cmp["summary"])  # {"green", "yellow", "red", "new", "reappeared", "total"}
```

### Reports

```python
cs.rollup("2026-05", carrier_id)           # period totals by status + by carrier
cs.attrition("2026-05", carrier_id)        # attrition rate for a period
cs.attrition_series(months=12)             # attrition trend
cs.data_quality("2026-05")                 # statement-quality signals (ok/watch/alert)
```

---

## Admin

Admin endpoints (require an `admin`-role session) live under `cs.admin`:

```python
cs.admin.list_accounts(status="pending")
cs.admin.account_overview(account_id)
cs.admin.metrics()
cs.admin.revenue()
```

---

## Pagination

List endpoints return a `data` list plus an optional `pagination` object:

```python
{
    "data": [...],
    "pagination": {"limit": 50, "offset": 0, "nextCursor": None, "hasMore": False},
}
```

Offset-based endpoints accept `limit` / `offset`; cursor-based ones (e.g. `list_files`) accept `limit` / `cursor` and return `nextCursor`.

---

## Error handling

Any non-2xx response raises an `ApiError`, carrying the HTTP `status` and the parsed [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) `problem+json` `body` when present.

```python
from commissionsight import ApiError

try:
    cs.get_job("does-not-exist")
except ApiError as err:
    print(err.status)       # e.g. 404
    print(str(err))         # problem `title`
    print(err.body)         # full problem+json payload
```

---

## Custom transport

Inject your own transport to use `requests`/`httpx`, add retries, or mock in tests. It takes `(method, url, headers, body)` and returns `(status_code, response_text)`:

```python
import requests

def transport(method, url, headers, body):
    r = requests.request(method, url, headers=headers, data=body)
    return r.status_code, r.text

cs = CommissionSightClient("https://api.commissionsight.com/v1", token="...", transport=transport)
```

---

## Links

- **Website:** https://commissionsight.com
- **API docs:** https://docs.commissionsight.com
- **TypeScript SDK:** https://github.com/commissionsight/sdk
- **Issues:** https://github.com/commissionsight/python-sdk/issues

## License

[MIT](./LICENSE) © CommissionSight
