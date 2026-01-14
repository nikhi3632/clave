"""Anthropic LLM provider implementation."""

import logging

import anthropic

from .base import (
    APIError,
    AuthenticationError,
    LLMError,
    LLMProvider,
    LLMResponse,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude LLM provider."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize the Anthropic provider.

        Args:
            api_key: Anthropic API key.
            model: Model name (default: claude-sonnet-4-20250514).
        """
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def _handle_error(self, e: Exception) -> None:
        """Convert Anthropic-specific errors to generic LLMError types."""
        if isinstance(e, anthropic.RateLimitError):
            raise RateLimitError("Rate limit exceeded, please try again later")

        if isinstance(e, anthropic.AuthenticationError):
            logger.error(f"Anthropic auth error: {e}")
            raise AuthenticationError("Service configuration error. Please contact support.")

        if isinstance(e, anthropic.APIStatusError):
            logger.error(f"Anthropic API error {e.status_code}: {e.message}")
            is_retryable = e.status_code >= 500 or e.status_code == 429
            raise APIError(
                "AI service is temporarily unavailable. Please try again.",
                status_code=e.status_code,
                retryable=is_retryable,
            )

        # Unknown error
        logger.error(f"Unexpected Anthropic error: {type(e).__name__}: {e}")
        raise LLMError(str(e), "UNKNOWN_ERROR", retryable=True)

    def _parse_response(self, response: anthropic.types.Message) -> LLMResponse:
        """Parse Anthropic response into LLMResponse."""
        content = response.content[0]
        if content.type != "text":
            raise LLMError("Unexpected response type from LLM", "INVALID_RESPONSE", True)

        return LLMResponse(
            content=content.text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

    async def complete(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Send async completion request to Anthropic."""
        try:
            kwargs: dict = {
                "model": self._model,
                "max_tokens": max_tokens,
                "messages": messages,
            }
            if system:
                kwargs["system"] = system

            response = self._client.messages.create(**kwargs)
            return self._parse_response(response)

        except (anthropic.RateLimitError, anthropic.AuthenticationError, anthropic.APIStatusError) as e:
            self._handle_error(e)
            raise  # Unreachable, but makes type checker happy

    def complete_sync(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Send synchronous completion request to Anthropic."""
        try:
            kwargs: dict = {
                "model": self._model,
                "max_tokens": max_tokens,
                "messages": messages,
            }
            if system:
                kwargs["system"] = system

            response = self._client.messages.create(**kwargs)
            return self._parse_response(response)

        except (anthropic.RateLimitError, anthropic.AuthenticationError, anthropic.APIStatusError) as e:
            self._handle_error(e)
            raise  # Unreachable, but makes type checker happy
