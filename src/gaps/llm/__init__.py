from .base import LLMProvider


def get_provider() -> LLMProvider:
    """The single place business logic asks for an LLM provider. Swapping
    Claude-via-Anthropic for Claude-via-Bedrock in production means
    changing this function only.
    """
    from .anthropic_provider import AnthropicProvider

    return AnthropicProvider()
