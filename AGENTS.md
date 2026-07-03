# AGENTS.md — Partner Strategy Workflow Copilot

## What this is
Internal tool that helps a Partner Strategy specialist resolve onboarding data gaps
faster. Input: an already-produced anomaly report. Output: routed, tracked gaps with
LLM-drafted customer outreach, gated by human approval.

## Stack
Python, Django REST Framework, Celery (SQS in prod / local broker in dev), PostgreSQL,
Claude via a provider interface (Bedrock is the production swap).

## Hard rules (never violate)
1. The LLM NEVER decides data validity, invents missing values, or estimates data.
   It ONLY drafts communication and summarizes gaps already present in the input report.
2. A draft may reference ONLY gap-IDs present in the source anomaly report. Anything
   else is a guardrail failure and must be rejected, not shown.
3. No outreach is ever "sent" without a human-approval step.
4. Routing, state, scheduling, and retries are DETERMINISTIC code — never LLM calls.
5. The LLM is called behind a provider interface. No direct SDK calls scattered in
   business logic.

## Context policy (static vs dynamic)
- Static (here, always loaded): these rules, the stack, the boundary.
- Dynamic (per task): anomaly-report contents, building/account context. Load on
  demand; do not inline into prompts globally.

## Verification (this is the deliverable)
- tests/ verify the DETERMINISTIC spine: given this report, routing produces exactly
  this record. Checked by code, pass/fail.
- evaluations/ verify the NON-DETERMINISTIC draft: groundedness (references only real
  gaps), hallucination (invents nothing), tone rubric (institutional asset manager).
- observability/ logs per run: model input/output, token cost, latency, eval scores.