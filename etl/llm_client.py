"""Simple synchronous LLM client for ETL operations."""

import logging
from dataclasses import dataclass, field

import anthropic

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from an LLM completion request."""

    content: str
    model: str
    usage: dict = field(default_factory=dict)


class LLMError(Exception):
    """Error during LLM operations."""

    def __init__(self, message: str, code: str = "LLM_ERROR", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class AnthropicClient:
    """Simple synchronous Anthropic client for ETL."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """Initialize the client."""
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete_sync(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Send synchronous completion request."""
        try:
            kwargs: dict = {
                "model": self._model,
                "max_tokens": max_tokens,
                "messages": messages,
            }
            if system:
                kwargs["system"] = system

            response = self._client.messages.create(**kwargs)

            content = response.content[0]
            if content.type != "text":
                raise LLMError("Unexpected response type", "INVALID_RESPONSE", True)

            return LLMResponse(
                content=content.text,
                model=response.model,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )

        except anthropic.RateLimitError:
            raise LLMError("Rate limit exceeded", "RATE_LIMIT", retryable=True)
        except anthropic.AuthenticationError:
            logger.error("Anthropic authentication error")
            raise LLMError("Authentication failed", "AUTH_ERROR", retryable=False)
        except anthropic.APIStatusError as e:
            logger.error(f"Anthropic API error {e.status_code}: {e.message}")
            raise LLMError(
                "API error", f"API_ERROR_{e.status_code}", retryable=e.status_code >= 500
            )
        except Exception as e:
            logger.error(f"Unexpected error: {type(e).__name__}: {e}")
            raise LLMError(str(e), "UNKNOWN_ERROR", retryable=True)


def get_client(
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
    provider: str = "anthropic",
) -> AnthropicClient:
    """Factory function to get an LLM client."""
    if provider != "anthropic":
        raise ValueError(f"Unsupported provider: {provider}. Only 'anthropic' is supported.")
    return AnthropicClient(api_key=api_key, model=model)
