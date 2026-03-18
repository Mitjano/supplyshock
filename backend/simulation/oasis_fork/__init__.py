"""SupplyShock OASIS Commodity Fork.

Self-contained fork of camel-ai/oasis adapted for commodity market simulation.
No dependency on camel-oasis PyPI package (which requires Python <3.12).

Architecture:
- SQLite per simulation (isolation)
- ActionType enum → platform handler dispatch via getattr()
- LLMAction uses Claude API for agent decisions
- ManualAction for rule-based agents (zero LLM cost)
"""

from .social_platform.typing import ActionType, DefaultPlatformType
from .social_agent.agent import SocialAgent
from .social_agent.agent_graph import AgentGraph
from .social_agent.agent_action import LLMAction, ManualAction
from .environment.env import OasisEnv

__all__ = [
    "ActionType",
    "DefaultPlatformType",
    "SocialAgent",
    "AgentGraph",
    "LLMAction",
    "ManualAction",
    "OasisEnv",
]
