"""LLM provider abstraction layer.

Usage:
    from llm import get_provider, LLMError

    provider = get_provider(api_key="sk-...", model="claude-sonnet-4-20250514")

    # Async (API)
    response = await provider.complete(
        messages=[{"role": "user", "content": "Hello"}],
        system="You are a helpful assistant.",
    )

    # Sync (ETL)
    response = provider.complete_sync(
        messages=[{"role": "user", "content": "Hello"}],
    )
"""

from .anthropic_provider import AnthropicProvider
from .base import (
    APIError,
    AuthenticationError,
    LLMError,
    LLMProvider,
    LLMResponse,
    RateLimitError,
)

__all__ = [
    # Factory
    "get_provider",
    # Base classes
    "LLMProvider",
    "LLMResponse",
    # Errors
    "LLMError",
    "RateLimitError",
    "AuthenticationError",
    "APIError",
    # Providers
    "AnthropicProvider",
]


def get_provider(
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
    provider: str = "anthropic",
) -> LLMProvider:
    """
    Factory function to get an LLM provider instance.

    Args:
        api_key: API key for the provider.
        model: Model name to use.
        provider: Provider name ("anthropic"). Extensible for future providers.

    Returns:
        LLMProvider instance.

    Raises:
        ValueError: If provider is not supported.
    """
    if provider == "anthropic":
        return AnthropicProvider(api_key=api_key, model=model)

    raise ValueError(f"Unsupported LLM provider: {provider}. Supported: anthropic")
