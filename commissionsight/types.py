"""Typed response shapes for the CommissionSight API.

These mirror the exported interfaces of the TypeScript SDK. They are ``TypedDict``
definitions (``total=False`` — the server may add or omit fields), so responses are
returned as plain ``dict`` objects you can index by key with editor autocomplete.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

try:  # Python 3.8+
    from typing import Literal, TypedDict
except ImportError:  # pragma: no cover
    from typing_extensions import Literal, TypedDict  # type: ignore

# A timestamp serializes as an epoch-millis int or an ISO string over JSON.
Timestamp = Union[int, str]

Status = Literal["green", "yellow", "red"]

Flag = Literal[
    "NEW",
    "COMMISSION_CHANGED",
    "DATA_CHANGED",
    "DROPPED",
    "REAPPEARED",
    "REAPPEARED_WITH_DELTA",
    "CHARGEBACK",
]

StabilityLevel = Literal["ok", "watch", "alert"]

ProductLine = Literal["major_medical", "medicare", "ancillary"]


class Pagination(TypedDict, total=False):
    limit: int
    offset: int
    nextCursor: Optional[int]
    hasMore: bool


class Page(TypedDict, total=False):
    """A list response: ``data`` plus optional ``pagination``."""

    data: List[Any]
    pagination: Pagination


class OriginalPayout(TypedDict, total=False):
    period: str
    amount: float
    fileId: Optional[str]
    fileName: Optional[str]


class ChargebackRow(TypedDict, total=False):
    memberRefId: str
    policyRefId: str
    memberExternalId: Optional[str]
    policyNumber: Optional[str]
    planName: Optional[str]
    chargebackAmount: float
    paidOut: bool
    originalPayout: Optional[OriginalPayout]
    fullyReversed: bool


class JobSummary(TypedDict, total=False):
    id: str
    carrierId: str
    periodYear: int
    periodMonth: int
    fileId: str
    r2Key: str
    status: Literal["queued", "processing", "completed", "failed"]
    stats: Optional[Dict[str, float]]
    error: Optional[str]
    webhookUrl: Optional[str]
    exceptionRowCount: int
    createdAt: Timestamp
    startedAt: Optional[Timestamp]
    completedAt: Optional[Timestamp]


class FileSummary(TypedDict, total=False):
    id: str
    accountId: str
    carrierId: str
    periodYear: int
    periodMonth: int
    originalFilename: str
    byteSize: int
    checksumSha256: str
    uploadedAt: Timestamp
    rescoreSuggested: bool
    r2PurgedAt: Optional[Timestamp]


class ResultRow(TypedDict, total=False):
    memberRefId: str
    policyRefId: Optional[str]
    status: Status
    flags: List[Flag]
    commissionAmount: Optional[float]
    prevCommissionAmount: Optional[float]
    commissionOwed: float
    comparedAgainstPeriod: Optional[str]
    memberExternalId: Optional[str]
    memberName: Optional[str]
    email: Optional[str]
    planName: Optional[str]
    policyNumber: Optional[str]
    premiumAmount: Optional[float]


class ComparisonRow(TypedDict, total=False):
    memberRefId: str
    status: Status
    flags: List[Flag]
    commissionAmount: Optional[float]
    prevCommissionAmount: Optional[float]
    comparedAgainstPeriod: Optional[str]
    memberName: Optional[str]
    memberExternalId: Optional[str]
    policyNumber: Optional[str]


class JourneyPolicy(TypedDict, total=False):
    policyRefId: str
    policyNumber: Optional[str]
    planName: Optional[str]
    planCode: Optional[str]
    commissionAmount: float
    premiumAmount: Optional[float]
    effectiveDate: Optional[str]
    renewalDate: Optional[str]


class JourneyDelta(TypedDict, total=False):
    field: str
    prevValue: Optional[str]
    currValue: Optional[str]


class JourneyPeriod(TypedDict, total=False):
    period: str
    periodYear: int
    periodMonth: int
    status: Optional[Status]
    flags: List[Flag]
    present: bool
    commissionAmount: Optional[float]
    prevCommissionAmount: Optional[float]
    premiumAmount: Optional[float]
    policies: List[JourneyPolicy]
    file: Optional[Dict[str, Any]]
    deltas: List[JourneyDelta]
    firstSeen: bool


class Journey(TypedDict, total=False):
    memberRefId: str
    policyRefId: str
    member: Dict[str, Any]
    firstPeriod: Optional[str]
    latestPeriod: Optional[str]
    periodCount: int
    periods: List[JourneyPeriod]


class TeamMember(TypedDict, total=False):
    id: str
    email: str
    role: Literal["member", "admin"]
    createdAt: Timestamp


class AuditEvent(TypedDict, total=False):
    id: str
    actor: str
    action: str
    target: Optional[str]
    meta: Optional[Dict[str, Any]]
    ip: Optional[str]
    createdAt: Timestamp


class BillingDetails(TypedDict, total=False):
    contactName: str
    companyName: str
    email: str
    phone: str
    addressLine1: str
    addressLine2: str
    city: str
    state: str
    postalCode: str
    country: str


class BillingProfile(BillingDetails, total=False):
    card: Optional[Dict[str, str]]
    paymentMethod: Optional[Literal["card", "us_bank_account"]]
    stripeEnabled: bool


class BillingPreview(TypedDict, total=False):
    period: Optional[str]
    members: int
    pricePerMemberCents: int
    amountCents: int
    method: Literal["card", "us_bank_account"]
    feeCents: int
    totalCents: int
    achSavingsCents: int
    surcharge: bool
    dueDate: Optional[str]
    custom: bool
    lastBilledPeriod: Optional[str]


class ExpectedCommissionRate(TypedDict, total=False):
    id: str
    carrierId: str
    planCode: Optional[str]
    rateType: Literal["percent_of_premium", "flat_per_member"]
    rateValue: float


class Webhook(TypedDict, total=False):
    id: str
    url: str
    events: List[str]


class AttritionPoint(TypedDict, total=False):
    period: str
    year: int
    month: int
    red: int
    memberCount: int
    attritionRate: float
    commissionAtRisk: float


class DataQualitySignal(TypedDict, total=False):
    carrierId: str
    carrierName: Optional[str]
    level: StabilityLevel
    reason: str
    droppedRate: float
    newRate: float
    churnOverlap: float
    red: int
    newMembers: int
    reappeared: int
    present: int


class DataQualityReport(TypedDict, total=False):
    period: Optional[str]
    overall: StabilityLevel
    carriers: List[DataQualitySignal]


# ``from`` is a Python keyword, so this TypedDict uses the functional syntax to keep
# the real JSON key name. Index it as ``range["from"]``.
CumulativeRange = TypedDict(
    "CumulativeRange",
    {
        "from": Optional[str],
        "to": Optional[str],
        "requestedFrom": Optional[str],
        "requestedTo": Optional[str],
        "periodsCovered": int,
    },
    total=False,
)


class CumulativeTotals(TypedDict, total=False):
    commissionOwed: float
    commissionAtRisk: float
    chargebackAmount: float
    chargebackCount: int
    red: int
    new: int
    reappeared: int
    owedEvaluated: int
    owedTotal: int
    # Cumulative coverage: Σ(owedEvaluated) ÷ Σ(owedTotal) across the range — NOT
    # the average of per-period coverage ratios.
    owedCoverage: float
    # A *volume*: the sum of per-period member counts (member-months), NOT a count of
    # distinct members. Use avgMembers / peakMembers for book-size figures.
    memberMonths: int
    avgMembers: float
    peakMembers: int
    owedEstimated: bool


class CumulativePeriod(TypedDict, total=False):
    period: str
    year: int
    month: int
    memberCount: int
    red: int
    new: int
    reappeared: int
    commissionAtRisk: float
    commissionOwed: float
    owedEvaluated: int
    owedTotal: int
    owedCoverage: float
    chargebackCount: int
    chargebackAmount: float


class CumulativeCarrier(TypedDict, total=False):
    carrierId: str
    carrierName: Optional[str]
    commissionOwed: float
    commissionAtRisk: float
    chargebackAmount: float
    owedEvaluated: int
    owedTotal: int
    owedCoverage: float
    memberMonths: int
    periodsCovered: int


class CumulativeReport(TypedDict, total=False):
    range: CumulativeRange
    totals: CumulativeTotals
    byPeriod: List[CumulativePeriod]
    byCarrier: List[CumulativeCarrier]


class InferredConfig(TypedDict, total=False):
    config: Any
    confidence: float
    headerRow: int
    sheets: List[str]
    mapped: List[Dict[str, Any]]
    unmapped: List[str]
    notes: List[str]
    preview: Optional[Dict[str, Any]]


class CarrierConfigEntry(TypedDict, total=False):
    id: str
    version: int
    fileType: Literal["csv", "xlsx"]
    accountId: Optional[str]
    isActive: bool
    config: Dict[str, Any]


class CarrierGroupMember(TypedDict, total=False):
    id: str
    name: str
    slug: str


class CarrierGroup(TypedDict, total=False):
    """A carrier brand (e.g. "UHC") and its per-product member carriers."""

    id: str
    name: str
    slug: str
    members: List[CarrierGroupMember]


class CarrierResolveCandidate(TypedDict, total=False):
    """One scored carrier candidate from :meth:`resolve_carrier`."""

    carrierId: str
    name: Optional[str]
    slug: Optional[str]
    productLine: ProductLine
    # 0..1 — how well this carrier's config fits the sample.
    confidence: float
    reason: str


class CarrierResolveResult(TypedDict, total=False):
    """Result of resolving a brand + sample file to a concrete carrier."""

    groupId: str
    ambiguous: bool
    best: Optional[CarrierResolveCandidate]
    ranked: List[CarrierResolveCandidate]


# --- Admin response shapes ---


class AdminMetrics(TypedDict, total=False):
    totalJobs: int
    jobsLast24h: int
    byStatus: Dict[str, int]
    failures: int
    accounts: int
    accountsByStatus: Dict[str, int]
    pendingAccounts: int
    users: int
    webhooks: Dict[str, int]
    webhooksPending: int
    webhooksFailed: int
    recentJobs: List[Dict[str, Any]]
    recentAccounts: List[Dict[str, Any]]


class AdminJobDetail(TypedDict, total=False):
    job: Dict[str, Any]
    carrierName: Optional[str]
    account: Optional[Dict[str, str]]
    file: Optional[Dict[str, Any]]
    durationMs: Optional[int]
    rescoreSuggested: bool


class AdminLogEvent(TypedDict, total=False):
    id: str
    ts: int
    level: Literal["info", "warn", "error"]
    source: Literal["job", "webhook"]
    message: str
    detail: Optional[str]


class AdminAlert(TypedDict, total=False):
    id: str
    severity: Literal["warning", "critical"]
    title: str
    detail: str
    ts: int


class AdminLogs(TypedDict, total=False):
    generatedAt: int
    events: List[AdminLogEvent]
    alerts: List[AdminAlert]
    pagination: Pagination


class AdminAccountOverview(TypedDict, total=False):
    account: Dict[str, str]
    counts: Dict[str, int]
    latestPeriod: Optional[str]
    rollup: Optional[Dict[str, float]]


class AdminAccountFile(TypedDict, total=False):
    id: str
    carrierId: str
    periodYear: int
    periodMonth: int
    originalFilename: str
    byteSize: int
    uploadedAt: Timestamp
    supersededAt: Optional[Timestamp]
    r2PurgedAt: Optional[Timestamp]


class AdminAccountJob(TypedDict, total=False):
    id: str
    carrierId: str
    periodYear: int
    periodMonth: int
    status: str
    error: Optional[str]
    stats: Optional[Dict[str, float]]
    createdAt: Timestamp
    completedAt: Optional[Timestamp]


class AdminAccountUser(TypedDict, total=False):
    id: str
    email: str
    role: str
    createdAt: Timestamp


class AdminCronRun(TypedDict, total=False):
    id: str
    ranAt: int
    requeued: int
    webhooksRedelivered: int
    filesPurged: int
    jobsCanceled: int
    billed: int
    durationMs: int


class AdminCronTask(TypedDict, total=False):
    key: str
    title: str
    description: str


class AdminSystemActivity(TypedDict, total=False):
    generatedAt: int
    tasks: List[AdminCronTask]
    runs: List[AdminCronRun]


class AdminRevenueSummary(TypedDict, total=False):
    generatedAt: int
    platform: Dict[str, Any]
    revenue: Dict[str, Any]
    ar: Dict[str, Any]
    carriers: List[Dict[str, Any]]


class AdminProvisionResult(TypedDict, total=False):
    provisioned: bool
    alreadyProvisioned: bool
    createdDatabase: bool
    migrationsApplied: int
    error: str


class AdminAccountBilling(TypedDict, total=False):
    accountId: str
    contactName: Optional[str]
    companyName: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    addressLine1: Optional[str]
    addressLine2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postalCode: Optional[str]
    country: Optional[str]
    customRateCents: Optional[int]
    surchargeEnabled: bool
    paymentMethodType: Optional[Literal["card", "us_bank_account"]]
    card: Optional[Dict[str, str]]
    lastBilledPeriod: Optional[str]
    lastBilledAmountCents: Optional[int]


class AdminUser(TypedDict, total=False):
    id: str
    email: str
    role: Literal["member", "admin"]
    accountId: Optional[str]
    accountName: Optional[str]
    createdAt: int
