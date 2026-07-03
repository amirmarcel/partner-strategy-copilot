"""Deterministic routing: raw anomaly -> tracked gap record.

No LLM or model I/O here — pure functions over plain dicts, so this is
cheaply unit-testable in isolation (tests land in the next session).
"""

from .models import TrackedGap

# gap_type -> owner_role. One owner role per gap type, observed consistently
# across every example in golden_dataset/examples.jsonl.
ROLE_BY_GAP_TYPE = {
    TrackedGap.GapType.MISSING_UTILITY_BILL: TrackedGap.OwnerRole.PROPERTY_MANAGER,
    TrackedGap.GapType.UNMATCHED_METER: TrackedGap.OwnerRole.ASSET_MANAGER,
    TrackedGap.GapType.INCOMPLETE_EQUIPMENT_INVENTORY: TrackedGap.OwnerRole.BUILDING_ENGINEER,
    TrackedGap.GapType.TENANT_OWNER_PAID_AMBIGUITY: TrackedGap.OwnerRole.ASSET_MANAGER,
}

# Single asset manager and building engineer cover every account in the
# current roster. Property managers are assigned per-account instead, since
# each portfolio has its own dedicated contact.
ASSET_MANAGER_NAME = "Priya Raman"
BUILDING_ENGINEER_NAME = "Marcus Feld"

PROPERTY_MANAGER_BY_ACCOUNT = {
    "Nuveen — Affordable Housing Fund II": "Dana Okafor",
    "LaSalle — Value-Add Fund III": "Tomás Herrera",
    "Topview Investments": "Benjamin White",
}


class UnroutableGap(Exception):
    """Raised when a raw anomaly can't be routed from the current roster."""


def _assign_owner(gap_type, account):
    role = ROLE_BY_GAP_TYPE.get(gap_type)
    if role is None:
        raise UnroutableGap(f"no owner_role mapping for gap_type={gap_type!r}")

    if role == TrackedGap.OwnerRole.ASSET_MANAGER:
        return role, ASSET_MANAGER_NAME
    if role == TrackedGap.OwnerRole.BUILDING_ENGINEER:
        return role, BUILDING_ENGINEER_NAME

    name = PROPERTY_MANAGER_BY_ACCOUNT.get(account)
    if name is None:
        raise UnroutableGap(
            f"no property_manager mapping for account={account!r}"
        )
    return role, name


def _normalize_severity(raw_severity):
    if raw_severity is None:
        raise UnroutableGap("anomaly is missing severity")
    normalized = str(raw_severity).strip().lower()
    if normalized not in TrackedGap.Severity.values:
        raise UnroutableGap(f"invalid severity={raw_severity!r}")
    return normalized


def route_anomaly(anomaly: dict) -> dict:
    """Route one raw anomaly (shaped like the "gap" object in
    golden_dataset/examples.jsonl) into a tracked gap record, ready to
    create a TrackedGap. Owner is assigned from the roster tables above;
    severity is normalized from the input, not inferred — the free-text
    detail field doesn't reliably determine urgency (see routing session
    notes), so we trust the upstream signal and fail loudly if it's absent
    or invalid rather than guess.
    """
    gap_type = anomaly["gap_type"]
    account = anomaly["account"]

    owner_role, owner_name = _assign_owner(gap_type, account)
    severity = _normalize_severity(anomaly.get("severity"))

    return {
        "gap_id": anomaly["gap_id"],
        "building": anomaly["building"],
        "building_id": anomaly["building_id"],
        "account": account,
        "gap_type": gap_type,
        "detail": anomaly["detail"],
        "owner_role": owner_role,
        "owner_name": owner_name,
        "severity": severity,
        "status": TrackedGap.Status.NEW,
    }
