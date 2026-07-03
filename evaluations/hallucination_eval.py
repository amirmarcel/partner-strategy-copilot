import re

# 2025-Q3 style
QUARTER_PATTERN = re.compile(r"\b20\d{2}-Q[1-4]\b")
# "March 2025" style
MONTH_YEAR_PATTERN = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+20\d{2}\b",
    re.IGNORECASE,
)
BARE_NUMBER_PATTERN = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")

DATE_PATTERNS = [QUARTER_PATTERN, MONTH_YEAR_PATTERN]

# Canonical 3-letter abbreviation for every month, keyed by any spelling
# MONTH_YEAR_PATTERN can match (abbreviated or full, case-insensitive).
_MONTH_CANONICAL = {
    "jan": "Jan", "january": "Jan",
    "feb": "Feb", "february": "Feb",
    "mar": "Mar", "march": "Mar",
    "apr": "Apr", "april": "Apr",
    "may": "May",
    "jun": "Jun", "june": "Jun",
    "jul": "Jul", "july": "Jul",
    "aug": "Aug", "august": "Aug",
    "sep": "Sep", "sept": "Sep", "september": "Sep",
    "oct": "Oct", "october": "Oct",
    "nov": "Nov", "november": "Nov",
    "dec": "Dec", "december": "Dec",
}
_MONTH_YEAR_TOKEN_PATTERN = re.compile(r"^([A-Za-z]+)\.?\s+(20\d{2})$")


def _normalize_date_token(token: str) -> str:
    """Canonicalize a MONTH_YEAR_PATTERN match's month word (e.g.
    "February 2025" -> "Feb 2025") so semantically-identical month
    phrasings compare equal. QUARTER_PATTERN matches (already "YYYY-QN")
    pass through unchanged, since they don't match this shape.
    """
    match = _MONTH_YEAR_TOKEN_PATTERN.match(token)
    if not match:
        return token
    month_word, year = match.group(1).lower(), match.group(2)
    canonical_month = _MONTH_CANONICAL.get(month_word)
    if canonical_month is None:
        return token
    return f"{canonical_month} {year}"
# Markdown/numbered-list markers ("1.", "2)") at the start of a line — these
# are structural, not data. Stripped before number extraction so a
# clarifying-question list doesn't read as fabricated figures.
_LIST_MARKER_PATTERN = re.compile(r"(?m)^\s*\d{1,2}[.)]\s+")
# Small ordinals ("1st", "2nd", "3rd", "4th", ...) — almost always
# enumeration/position language, not invented data. Stripped for the same
# reason; genuinely fabricated figures (kWh, capacities, years) don't take
# this form.
_ORDINAL_PATTERN = re.compile(r"\b\d{1,2}(?:st|nd|rd|th)\b", re.IGNORECASE)


def _strip_non_data_numbers(text: str) -> str:
    text = _LIST_MARKER_PATTERN.sub("", text)
    text = _ORDINAL_PATTERN.sub("", text)
    return text


def _tokens(text: str, patterns) -> set:
    found = set()
    for pattern in patterns:
        found.update(m.group(0) for m in pattern.finditer(text))
    return found


def evaluate_hallucination(draft: str, gap: dict, labels: dict) -> dict:
    """HEURISTIC, not semantic. Flags numeric and date-like tokens in the
    draft that appear nowhere in this gap's own source data (detail,
    gap_id, building_id) or in its expected must_mention strings.

    Coverage: this catches literal fabricated figures/dates — a real chunk
    of the must_not_invent items in golden_dataset/examples.jsonl (invented
    kWh figures, capacity numbers, dates outside the stated window). It
    CANNOT detect fabricated assertions with no attached number, e.g.
    concluding an ambiguous meter "is tenant-paid" when the source only
    raises the question. Do not treat a pass here as proof the draft
    invents nothing — read must_not_invent in the labels for the full
    intended scope, and treat this as a partial, string-level signal.
    """
    allowed_text = " ".join([
        gap.get("detail", ""),
        gap.get("gap_id", ""),
        gap.get("building_id", ""),
        " ".join(labels.get("must_mention", [])),
    ])

    draft_for_numbers = _strip_non_data_numbers(draft)
    allowed_for_numbers = _strip_non_data_numbers(allowed_text)
    draft_numbers = _tokens(draft_for_numbers, [BARE_NUMBER_PATTERN])
    allowed_numbers = _tokens(allowed_for_numbers, [BARE_NUMBER_PATTERN])
    fabricated_numbers = sorted(draft_numbers - allowed_numbers)

    draft_dates = {_normalize_date_token(t) for t in _tokens(draft, DATE_PATTERNS)}
    allowed_dates = {_normalize_date_token(t) for t in _tokens(allowed_text, DATE_PATTERNS)}
    fabricated_dates = sorted(draft_dates - allowed_dates)

    violations = []
    if fabricated_numbers:
        violations.append(
            "numeric figures not grounded in source: " + ", ".join(fabricated_numbers)
        )
    if fabricated_dates:
        violations.append(
            "dates not grounded in source: " + ", ".join(fabricated_dates)
        )

    return {
        "passed": not violations,
        "violations": violations,
        "coverage_note": (
            "heuristic numeric/date matching only — does not detect "
            "fabricated assertions without an attached number or date"
        ),
    }
