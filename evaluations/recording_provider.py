import time


class RecordingProvider:
    """Wraps an LLMProvider to capture prompt/response/latency/token usage
    for observability, without adding to or changing the LLMProvider
    contract (still just complete(prompt) -> str). Every call the wrapped
    provider makes goes through this, so nothing here bypasses the
    provider interface (AGENTS.md Rule 5).

    Token usage is read opportunistically from a `last_usage` attribute if
    the wrapped provider happens to set one (AnthropicProvider does); other
    providers simply won't have usage logged.
    """

    def __init__(self, inner):
        self._inner = inner
        self.calls = []

    def complete(self, prompt: str) -> str:
        start = time.perf_counter()
        response = self._inner.complete(prompt)
        latency_ms = (time.perf_counter() - start) * 1000

        self.calls.append({
            "prompt": prompt,
            "response": response,
            "latency_ms": round(latency_ms, 1),
            "token_usage": getattr(self._inner, "last_usage", None),
        })
        return response

    @property
    def last_call(self):
        return self.calls[-1] if self.calls else None
