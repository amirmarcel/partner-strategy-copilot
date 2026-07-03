import re
from dataclasses import dataclass, field


@dataclass
class GroundednessResult:
    is_grounded: bool
    violations: list[str] = field(default_factory=list)


def _id_prefix(identifier: str) -> str:
    return identifier.split("-", 1)[0]


def _foreign_ids(text: str, allowed_id: str) -> list[str]:
    """IDs in `text` that share allowed_id's prefix (e.g. "G-", "BLD-")
    but aren't allowed_id itself.
    """
    prefix = re.escape(_id_prefix(allowed_id))
    pattern = rf"\b{prefix}-[A-Za-z0-9]+\b"
    found = set(re.findall(pattern, text))
    return sorted(found - {allowed_id})


def check_groundedness(draft: str, gap: dict) -> GroundednessResult:
    """Deterministic guardrail enforcing AGENTS.md Rule 2: a draft may
    reference only identifiers belonging to the single gap it was drafted
    for. No LLM involved — plain string/regex checks over the draft text
    and the routed gap record produced by route_anomaly.

    Catches structured identifier leaks: a stray gap ID, or a different
    building's BLD-xxx code slipping into the draft. Does NOT catch
    prose-level scope violations with no ID attached (e.g. a building named
    only by description, or speculative detail language restated as fact)
    — those require semantic judgment and belong to the eval suite, not
    this guardrail.
    """
    violations = []

    foreign_gap_ids = _foreign_ids(draft, gap["gap_id"])
    if foreign_gap_ids:
        violations.append(
            "references gap ID(s) not allowed for this gap: "
            + ", ".join(foreign_gap_ids)
        )

    foreign_building_ids = _foreign_ids(draft, gap["building_id"])
    if foreign_building_ids:
        violations.append(
            "references building ID(s) not allowed for this gap: "
            + ", ".join(foreign_building_ids)
        )

    return GroundednessResult(is_grounded=not violations, violations=violations)
