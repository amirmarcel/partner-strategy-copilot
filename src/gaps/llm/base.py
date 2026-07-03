from typing import Protocol


class LLMProvider(Protocol):
    """Anything that can turn a prompt into text. The only surface the rest
    of the app is allowed to depend on for model access (AGENTS.md Rule 5).
    """

    def complete(self, prompt: str) -> str:
        ...
