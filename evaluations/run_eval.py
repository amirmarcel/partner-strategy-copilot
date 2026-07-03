"""Starter eval harness for the drafting step (draft_outreach), scored
against golden_dataset/examples.jsonl.

STARTER SCALE, NOT PRODUCTION: 11 hand-labeled examples, run sequentially,
no parallelism, no retries, no eval-set versioning, no CI wiring. Good
enough to catch regressions during development of the prompt/guardrails;
not a substitute for a larger, continuously-maintained eval set before
this ships.

Usage: .venv/bin/python evaluations/run_eval.py
(run from the repo root, or anywhere — paths are resolved relative to
this file)
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()

from gaps.drafting import draft_outreach  # noqa: E402
from gaps.llm import get_provider  # noqa: E402
from gaps.routing import route_anomaly  # noqa: E402

from evaluations.groundedness_eval import evaluate_groundedness  # noqa: E402
from evaluations.hallucination_eval import evaluate_hallucination  # noqa: E402
from evaluations.recording_provider import RecordingProvider  # noqa: E402
from evaluations.tone_eval import evaluate_tone  # noqa: E402

EXAMPLES_PATH = REPO_ROOT / "golden_dataset" / "examples.jsonl"
OBSERVABILITY_DIR = REPO_ROOT / "observability"

EVAL_DIMENSIONS = ["groundedness", "hallucination", "tone"]


def load_examples() -> list[dict]:
    with EXAMPLES_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_one(example: dict, provider) -> dict:
    gap = example["gap"]
    labels = example["labels"]

    draft_recorder = RecordingProvider(provider)
    tone_recorder = RecordingProvider(provider)

    routed = route_anomaly(gap)
    draft = draft_outreach(routed, provider=draft_recorder)

    groundedness = evaluate_groundedness(draft, routed, labels)
    hallucination = evaluate_hallucination(draft, routed, labels)
    tone = evaluate_tone(draft, labels.get("tone_notes", ""), tone_recorder)

    return {
        "example_id": example["id"],
        "gap_id": gap["gap_id"],
        "draft": draft,
        "model_io": {
            "draft_call": draft_recorder.last_call,
            "tone_judge_call": tone_recorder.last_call,
        },
        "eval": {
            "groundedness": groundedness,
            "hallucination": hallucination,
            "tone": tone,
        },
    }


def summarize(results: list[dict]) -> dict:
    n = len(results)
    pass_counts = {
        dim: sum(1 for r in results if r["eval"][dim]["passed"])
        for dim in EVAL_DIMENSIONS
    }
    overall_pass = sum(
        1 for r in results if all(r["eval"][dim]["passed"] for dim in EVAL_DIMENSIONS)
    )
    total_latency_ms = sum(
        (r["model_io"]["draft_call"] or {}).get("latency_ms", 0)
        + (r["model_io"]["tone_judge_call"] or {}).get("latency_ms", 0)
        for r in results
    )
    return {
        "note": "starter eval harness — 11 examples, not production-scale",
        "n_examples": n,
        "pass_rates": {dim: f"{pass_counts[dim]}/{n}" for dim in EVAL_DIMENSIONS},
        "overall_pass": f"{overall_pass}/{n}",
        "total_latency_ms": round(total_latency_ms, 1),
        "hallucination_eval_coverage_note": (
            "heuristic numeric/date matching only — see "
            "evaluations/hallucination_eval.py docstring"
        ),
    }


def run():
    provider = get_provider()
    examples = load_examples()
    results = []

    for example in examples:
        result = run_one(example, provider)
        results.append(result)
        e = result["eval"]
        print(
            f"{result['example_id']} ({result['gap_id']}): "
            f"groundedness={'PASS' if e['groundedness']['passed'] else 'FAIL'} "
            f"hallucination={'PASS' if e['hallucination']['passed'] else 'FAIL'} "
            f"tone={'PASS' if e['tone']['passed'] else 'FAIL'}"
        )

    summary = summarize(results)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = OBSERVABILITY_DIR / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nWritten to {run_dir}")

    return results, summary


if __name__ == "__main__":
    run()
