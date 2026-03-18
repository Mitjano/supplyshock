"""Agent action types — LLMAction (Claude-driven) and ManualAction (scripted).

LLMAction: agent observes environment, LLM decides action + args.
ManualAction: pre-scripted action (zero LLM cost).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..social_platform.typing import ActionType


@dataclass
class LLMAction:
    """Let the LLM model decide the agent's action this step.

    The agent will:
    1. Observe environment (market events, price consensus)
    2. Call Claude API with system prompt + observation
    3. Parse response to extract action type + args
    """
    pass


@dataclass
class ManualAction:
    """Pre-scripted action — no LLM call needed.

    Usage:
        ManualAction(ActionType.CREATE_POST, {"content": "Breaking news..."})
        ManualAction(ActionType.DO_NOTHING, {})
    """
    action_type: ActionType
    action_args: dict[str, Any] = field(default_factory=dict)
