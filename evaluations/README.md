# Evaluations

Scores the drafting step (`gaps.drafting.draft_outreach`) against the 11
labeled examples in `golden_dataset/examples.jsonl`.

**This is a starter eval harness, not production-scale.** 11 hand-labeled
examples, sequential execution, no parallelism, no retries, no eval-set
versioning, no CI wiring. It's enough to catch regressions while
developing the prompt and guardrails — not a substitute for a larger,
continuously maintained eval set before this ships.

This is distinct from `src/gaps/tests.py`: those are unit tests of the
deterministic routing spine (pass/fail, checked by code). These evals
score non-deterministic LLM output against labels.

## Run it

```
.venv/bin/python evaluations/run_eval.py
```

Requires `ANTHROPIC_API_KEY` set (via `.env`, see `.env.example`) — this
makes real API calls (one drafting call + one tone-judge call per
example).

## Dimensions

- **Groundedness** (`groundedness_eval.py`, deterministic) — reuses
  `gaps.guardrails.check_groundedness` (foreign gap/building ID check) and
  additionally checks every `must_mention` string appears in the draft and
  no `forbidden_references` string does.
- **Hallucination** (`hallucination_eval.py`, heuristic) — flags numeric
  and date-like tokens in the draft with no basis in the source data.
  **Known limitation:** this is string/number/date matching, not semantic
  detection. It cannot catch a fabricated *assertion* that has no attached
  number (e.g. resolving "is this meter tenant-paid?" into a stated fact
  when the source only raises the question) — several `must_not_invent`
  items in the dataset are exactly this kind of trap and are outside this
  eval's coverage. Treat a pass here as a partial signal, not proof of no
  hallucination.
- **Tone** (`tone_eval.py`, LM judge) — sends the draft and the example's
  own `tone_notes` (used as a per-example rubric) to the LLM through the
  provider interface, asking for 1-5 scores on specificity,
  professionalism, single-clear-ask, and rubric adherence. Pass threshold
  is a starter value (4/5 on every dimension) — tune once real drafts have
  been reviewed by a human.

## Output

Each run writes to `observability/runs/<UTC timestamp>/`:
- `results.json` — per-example draft, eval results, and model I/O
  (prompt, response, latency, token usage where available)
- `summary.json` — pass rates per dimension across the run
