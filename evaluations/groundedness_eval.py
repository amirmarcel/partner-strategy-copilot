import re

from gaps.guardrails import check_groundedness

_QUARTER_WORDS = {
    "first": "Q1", "1st": "Q1",
    "second": "Q2", "2nd": "Q2",
    "third": "Q3", "3rd": "Q3",
    "fourth": "Q4", "4th": "Q4",
}
_QUARTER_WORD_PATTERN = re.compile(
    r"\b(" + "|".join(_QUARTER_WORDS) + r")\s+quarter\s+(?:of\s+)?(\d{4})\b",
    re.IGNORECASE,
)
# "Q3 2025" or "Q3-2025" -> canonical "2025-Q3". Deliberately does NOT match
# the already-canonical "2025-Q3" form (year comes first there).
_QUARTER_LOOSE_PATTERN = re.compile(r"\bQ([1-4])[\s-](\d{4})\b", re.IGNORECASE)


def _normalize_quarters(text: str) -> str:
    """Rewrite prose/alternate quarter phrasing into canonical YYYY-QN, so
    must_mention checks aren't defeated by semantically-identical
    formatting (e.g. "Q3 2025" or "third quarter of 2025" vs "2025-Q3").
    Not exhaustive date NLP — covers the phrasing patterns observed in
    golden_dataset/examples.jsonl. Only used for the must_mention
    comparison below; forbidden_references and the foreign-ID guardrail
    are untouched by this normalization.
    """
    text = _QUARTER_WORD_PATTERN.sub(
        lambda m: f"{m.group(2)}-{_QUARTER_WORDS[m.group(1).lower()]}", text
    )
    text = _QUARTER_LOOSE_PATTERN.sub(
        lambda m: f"{m.group(2)}-Q{m.group(1)}", text
    )
    return text


def evaluate_groundedness(draft: str, gap: dict, labels: dict) -> dict:
    """Deterministic. Stricter than gaps.guardrails.check_groundedness
    alone: it reuses that guardrail's foreign-ID check (Rule 2) AND checks
    the example's labels — every string in must_mention must appear in the
    draft, and no string in forbidden_references may appear. No LLM
    involved; this is substring matching against the golden labels.

    must_mention comparison is case-insensitive and quarter-format
    normalized (see _normalize_quarters), so a draft that correctly says
    "Q3 2025" instead of literal "2025-Q3" isn't penalized for phrasing.
    forbidden_references and the foreign-ID guardrail stay exact-match —
    those exist specifically to catch leaked identifiers and out-of-scope
    references, and loosening them would defeat the point.
    """
    violations = []

    guardrail_result = check_groundedness(draft, gap)
    violations.extend(guardrail_result.violations)

    normalized_draft = _normalize_quarters(draft).lower()
    missing_mentions = [
        s
        for s in labels.get("must_mention", [])
        if _normalize_quarters(s).lower() not in normalized_draft
    ]
    if missing_mentions:
        violations.append(
            "missing required mentions: " + ", ".join(missing_mentions)
        )

    forbidden_hits = [
        s for s in labels.get("forbidden_references", []) if s in draft
    ]
    if forbidden_hits:
        violations.append(
            "contains forbidden references: " + ", ".join(forbidden_hits)
        )

    return {"passed": not violations, "violations": violations}
