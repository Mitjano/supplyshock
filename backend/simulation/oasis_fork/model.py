"""LLM model adapters for OASIS commodity fork.

Wraps Claude API (via anthropic SDK) for agent decision-making.
Compatible with SocialAgent.decide() interface.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class ClaudeModel:
    """Anthropic Claude model adapter.

    Usage:
        model = ClaudeModel("claude-haiku-4-5-20251001")
        response = model.complete(system="...", messages=[...])
    """

    def __init__(
        self,
        model_id: str = "claude-haiku-4-5-20251001",
        api_key: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        timeout: float = 30.0,
    ):
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

        # Lazy import — only needed when LLM agents are used
        try:
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=api_key or os.environ.get("ANTHROPIC_API_KEY", ""),
                timeout=timeout,
            )
        except ImportError:
            raise ImportError(
                "anthropic package required for LLM agents. "
                "Install with: pip install anthropic"
            )

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        """Call Claude API and return text response.

        Raises on timeout (configured in __init__) or API error.
        """
        try:
            response = self._client.messages.create(
                model=self.model_id,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system,
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            logger.error("Claude API error (%s): %s", self.model_id, e)
            raise


class MockModel:
    """Mock model for testing — returns deterministic responses."""

    def __init__(self, default_response: str | None = None):
        self._default = default_response or '{"action": "do_nothing"}'
        self._responses: list[str] = []
        self._call_count = 0

    def add_response(self, response: str) -> None:
        """Queue a response for the next complete() call."""
        self._responses.append(response)

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        """Return queued response or default."""
        self._call_count += 1
        if self._responses:
            return self._responses.pop(0)
        return self._default

    @property
    def call_count(self) -> int:
        return self._call_count
