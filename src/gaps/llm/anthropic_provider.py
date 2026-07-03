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
        # Populated after each complete() call, for observability
        # (evaluations/recording_provider.py reads this opportunistically).
        # Not part of the LLMProvider contract — other providers need not
        # set it.
        self.last_usage = None

    def complete(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        self.last_usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return response.content[0].text
