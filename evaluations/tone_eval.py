import json
import re

DIMENSIONS = ["specificity", "professionalism", "single_clear_ask", "rubric_adherence"]

# Starter threshold: every dimension must score at least this to pass.
# Tune once real drafts have been reviewed by a human.
PASS_THRESHOLD = 4

JUDGE_PROMPT_TEMPLATE = """You are scoring a drafted outreach message for tone \
and quality. This message was drafted by another AI system on behalf of a \
Partner Strategy specialist and will be reviewed by a human before it is ever \
sent.

Tone rubric for this specific message (read carefully — it may describe \
traps the draft must avoid, not just a general style guide):
{tone_notes}

Draft to score:
---
{draft}
---

Score the draft from 1 (fails badly) to 5 (excellent) on each dimension:
- specificity: is the ask precise and grounded in the gap described, not vague?
- professionalism: institutional asset-manager tone — polite, not apologetic?
- single_clear_ask: does it make one unambiguous request rather than several or none?
- rubric_adherence: does it follow the specific notes above, including avoiding \
any traps they describe?

Respond with ONLY a JSON object, no other text, in exactly this shape:
{{"specificity": <1-5>, "professionalism": <1-5>, "single_clear_ask": <1-5>, \
"rubric_adherence": <1-5>, "justification": "<one line>"}}
"""


def _build_judge_prompt(draft: str, tone_notes: str) -> str:
    return JUDGE_PROMPT_TEMPLATE.format(draft=draft, tone_notes=tone_notes)


def _parse_json_response(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def evaluate_tone(draft: str, tone_notes: str, provider) -> dict:
    """LM-judge eval, NOT deterministic. Sends the draft plus this example's
    tone_notes (the per-example rubric) to the LLM through the provider
    interface (never the SDK directly — AGENTS.md Rule 5) and asks for
    1-5 scores across four dimensions plus a one-line justification.
    """
    prompt = _build_judge_prompt(draft, tone_notes)
    response_text = provider.complete(prompt)
    scores = _parse_json_response(response_text)

    if scores is None:
        return {
            "passed": False,
            "error": "could not parse judge response as JSON",
            "raw_response": response_text,
        }

    dimension_scores = {d: scores.get(d) for d in DIMENSIONS}
    passed = all(
        isinstance(v, (int, float)) and v >= PASS_THRESHOLD
        for v in dimension_scores.values()
    )

    return {
        "passed": passed,
        "scores": dimension_scores,
        "justification": scores.get("justification"),
        "threshold": PASS_THRESHOLD,
    }
