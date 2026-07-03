import os

import anthropic

# Smaller/cheaper Claude model — sufficient for drafting a short outreach
# message from structured context. Override via ANTHROPIC_MODEL.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

MAX_TOKENS = 1024


class AnthropicProvider:
    """The only file in this codebase that imports the anthropic SDK."""

    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env "
                "and fill it in."
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)

    def complete(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
