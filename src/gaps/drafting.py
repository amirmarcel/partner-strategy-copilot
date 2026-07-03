from .llm import LLMProvider, get_provider

STATIC_INSTRUCTIONS = """You are drafting a short outreach message on behalf of a \
Partner Strategy specialist, addressed to the person who can resolve a specific \
data gap found during portfolio onboarding.

Rules you must follow exactly:
1. You do not have authority to decide whether data is valid, invent missing \
values, or estimate any figure, date, or fact. You may only summarize the gap \
exactly as described below and ask for what is missing.
2. Reference ONLY the gap ID given below. Do not mention any other gap, building, \
or account, even if one is named in the detail text.
3. If the gap description contains ambiguity (for example, it is unclear who pays \
for something, or which of several options is correct), your message must ask a \
clarifying question and present the open possibilities. Do NOT assert or pick an \
answer.
4. Do not restate speculation, hints, or notes in the source detail (words like \
"appears", "presumably", "usually", "likely") as if they were confirmed facts.
5. Output ONLY the message body. No subject line, no meta-commentary, no preamble \
such as "Here is a draft".

Tone: institutional asset manager. Polite, specific, not apologetic. One clear ask.
"""


def _build_prompt(gap: dict) -> str:
    context = (
        f"Gap ID: {gap['gap_id']}\n"
        f"Building: {gap['building']}\n"
        f"Account: {gap['account']}\n"
        f"Gap type: {gap['gap_type']}\n"
        f"Detail (verbatim from the anomaly report): {gap['detail']}\n"
        f"Addressed to: {gap['owner_name']} ({gap['owner_role']})\n"
    )
    return f"{STATIC_INSTRUCTIONS}\n---\n{context}"


def draft_outreach(gap: dict, provider: LLMProvider | None = None) -> str:
    """Draft an outreach message for a routed gap record (the dict shape
    route_anomaly produces). Only calls the LLM through the provider
    interface — never the Anthropic SDK directly (AGENTS.md Rule 5).

    This function does not enforce groundedness; that's a separate
    deterministic check (see guardrails.py) run on the returned draft.
    """
    provider = provider or get_provider()
    prompt = _build_prompt(gap)
    return provider.complete(prompt)
