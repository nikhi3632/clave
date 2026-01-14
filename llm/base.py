"""Abstract LLM provider interface and error classes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    """Response from an LLM completion request."""

    content: str
    model: str
    usage: dict = field(default_factory=dict)


class LLMError(Exception):
    """Base error for LLM operations."""

    def __init__(self, message: str, code: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class RateLimitError(LLMError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "RATE_LIMIT", retryable=True)


class AuthenticationError(LLMError):
    """Authentication failed (invalid API key)."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTH_ERROR", retryable=False)


class APIError(LLMError):
    """Generic API error."""

    def __init__(self, message: str, status_code: int | None = None, retryable: bool = True):
        code = f"API_ERROR_{status_code}" if status_code else "API_ERROR"
        super().__init__(message, code, retryable=retryable)
        self.status_code = status_code


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Send an async completion request to the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            system: Optional system prompt.
            max_tokens: Maximum tokens in the response.

        Returns:
            LLMResponse with content, model, and usage info.

        Raises:
            LLMError: On any LLM-related error.
        """
        pass

    @abstractmethod
    def complete_sync(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Send a synchronous completion request to the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            system: Optional system prompt.
            max_tokens: Maximum tokens in the response.

        Returns:
            LLMResponse with content, model, and usage info.

        Raises:
            LLMError: On any LLM-related error.
        """
        pass
