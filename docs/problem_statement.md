# Problem Statement — Partner Strategy Workflow Copilot

## Problem
When the company onboards a new portfolio, its product detects data gaps and anomalies
(missing utility bills, unmatched meters, incomplete equipment inventory). Someone
still has to turn each detected gap into a specific, correctly-addressed request to
the right person at the customer — and chase it to resolution before the 30-day
onboarding clock runs out.

## User
The internal Partner Strategy / Customer Success specialist. NOT the customer.
(Former real-estate operators, fluent in buildings/energy/compliance.)

## What they do today
Read the anomaly report. For each gap, figure out which building, which account, who
owns it, and how urgent it is. Manually draft outreach to the right property manager.
Track who has responded across dozens of buildings and many parties. Repeat until the
portfolio is complete or the SLA is breached.

## Transformation
anomaly report (input) → deterministic routing (building / account / owner / severity)
→ tracked status record → LLM-drafted outreach for the gap → human approval → status
tracking. The specialist reviews and sends; they never start from a blank page or lose
track of what's outstanding.

## Metric
Specialist minutes per resolved gap, and share of gaps resolved within the 30-day SLA.
Before: manual triage + drafting + spreadsheet tracking. After: review-and-approve.

## Boundary (what this is NOT)
This does not detect, validate, or estimate data — the company's product already does
that, and it is their core advantage. This tool operates strictly downstream of an
already-produced anomaly report. It is internal leverage for the team, not a product
feature.