"""SocialAgent — the core agent class for OASIS commodity fork.

Each agent has:
- user_info (UserInfo or CommodityAgentInfo)
- environment (SocialEnvironment or CommodityEnvironment)
- available_actions (list of ActionType)
- model (for LLM-driven decisions) or None (rule-based)
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import TYPE_CHECKING, Any

from .agent_environment import (
    CommodityEnvironment,
    SocialAction,
    SocialEnvironment,
)
from ..social_platform.config.user import CommodityAgentInfo, UserInfo
from ..social_platform.typing import ActionType

if TYPE_CHECKING:
    from .agent_graph import AgentGraph

logger = logging.getLogger(__name__)


class SocialAgent:
    """Agent that participates in the OASIS simulation.

    Can be LLM-driven (model is set) or rule-based (model is None).
    """

    def __init__(
        self,
        agent_id: int,
        user_info: UserInfo | CommodityAgentInfo,
        agent_graph: AgentGraph,
        model: Any = None,
        tools: list | None = None,
        available_actions: list[ActionType] | None = None,
    ):
        self.agent_id = agent_id
        self.user_info = user_info
        self.agent_graph = agent_graph
        self.model = model
        self.tools = tools or []
        self.available_actions = available_actions or [ActionType.DO_NOTHING]

        # Environment and action proxy are set when env.reset() is called
        self.env: SocialEnvironment | CommodityEnvironment | None = None
        self.action: SocialAction | None = None
        self.system_message = user_info.to_system_message()

    def setup(self, channel, db_path: str | None = None) -> None:
        """Initialize agent's action proxy and environment.

        Called by OasisEnv.reset().
        """
        self.action = SocialAction(self.agent_id, channel)

        # Route to CommodityEnvironment if agent has CommodityAgentInfo
        if isinstance(self.user_info, CommodityAgentInfo):
            self.env = CommodityEnvironment(
                self.action,
                db_path=db_path,
                commodity=self.user_info.commodity,
            )
        else:
            self.env = SocialEnvironment(self.action)

    async def observe(self) -> str:
        """Get current environment observation as text."""
        if self.env is None:
            return "Environment not initialized."
        return await self.env.to_text_prompt()

    async def decide(self, observation: str) -> tuple[ActionType, dict[str, Any]]:
        """Use LLM to decide action based on observation.

        Returns (action_type, action_args) tuple.
        """
        if self.model is None:
            return ActionType.DO_NOTHING, {}

        # Build messages for Claude API
        messages = [
            {"role": "user", "content": observation},
        ]

        try:
            response = self.model.complete(
                system=self.system_message,
                messages=messages,
            )
            return self._parse_llm_response(response)
        except Exception as e:
            logger.error(
                "LLM decision failed for agent %d: %s", self.agent_id, e
            )
            return ActionType.DO_NOTHING, {}

    def _parse_llm_response(
        self, response: str
    ) -> tuple[ActionType, dict[str, Any]]:
        """Parse LLM JSON response into action type and args."""
        try:
            # Try parsing entire response as JSON first
            data = None
            stripped = response.strip()

            # Remove markdown code block wrapping if present
            if stripped.startswith("```"):
                # Extract content between ``` markers
                lines = stripped.split("\n")
                json_lines = []
                inside = False
                for line in lines:
                    if line.strip().startswith("```") and not inside:
                        inside = True
                        continue
                    elif line.strip() == "```" and inside:
                        break
                    elif inside:
                        json_lines.append(line)
                if json_lines:
                    stripped = "\n".join(json_lines).strip()

            # Try direct parse
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                # Fallback: find first { and match to its closing }
                start = stripped.find("{")
                if start != -1:
                    depth = 0
                    for i in range(start, len(stripped)):
                        if stripped[i] == "{":
                            depth += 1
                        elif stripped[i] == "}":
                            depth -= 1
                            if depth == 0:
                                try:
                                    data = json.loads(stripped[start:i + 1])
                                except json.JSONDecodeError:
                                    pass
                                break

            if data is None or not isinstance(data, dict):
                logger.warning(
                    "Agent %d: no valid JSON in response: %s",
                    self.agent_id, response[:200],
                )
                return ActionType.DO_NOTHING, {}
            action_str = data.get("action", "do_nothing")

            # Map action string to ActionType
            action_map = {
                "submit_trade": ActionType.SUBMIT_TRADE,
                "update_price_view": ActionType.UPDATE_PRICE_VIEW,
                "reroute_vessel": ActionType.REROUTE_VESSEL,
                "impose_measure": ActionType.IMPOSE_MEASURE,
                "activate_inventory": ActionType.ACTIVATE_INVENTORY,
                "create_post": ActionType.CREATE_POST,
                "do_nothing": ActionType.DO_NOTHING,
            }

            action_type = action_map.get(action_str, ActionType.DO_NOTHING)

            # Validate action is in agent's available actions
            if action_type not in self.available_actions:
                logger.warning(
                    "Agent %d tried %s but only has %s",
                    self.agent_id, action_type,
                    [a.value for a in self.available_actions],
                )
                return ActionType.DO_NOTHING, {}

            # Build args from parsed data
            args = {}
            if action_type == ActionType.SUBMIT_TRADE:
                args = {
                    "commodity": data.get("commodity", "coal"),
                    "action": data.get("trade_action", "hold"),
                    "volume_mt": float(data.get("volume_mt", 0)),
                    "price_view": float(data.get("price_view", 0)),
                }
            elif action_type == ActionType.UPDATE_PRICE_VIEW:
                args = {
                    "commodity": data.get("commodity", "coal"),
                    "price_usd": float(data.get("price_usd", 0)),
                    "confidence": float(data.get("confidence", 0.5)),
                }
            elif action_type == ActionType.REROUTE_VESSEL:
                args = {
                    "mmsi": int(data.get("mmsi", 0)),
                    "original_port": data.get("original_port", ""),
                    "new_port": data.get("new_port", ""),
                    "reason": data.get("reason", "disruption"),
                }
            elif action_type == ActionType.IMPOSE_MEASURE:
                args = {
                    "measure_type": data.get("measure_type", "sanction"),
                    "commodity": data.get("commodity", "coal"),
                    "affected_region": data.get("affected_region", ""),
                    "duration_days": int(data.get("duration_days", 30)),
                }
            elif action_type == ActionType.ACTIVATE_INVENTORY:
                args = {
                    "commodity": data.get("commodity", "coal"),
                    "volume_mt": float(data.get("volume_mt", 0)),
                    "reason": data.get("reason", "disruption"),
                }
            elif action_type == ActionType.CREATE_POST:
                args = {"content": data.get("content", "")}

            return action_type, args

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(
                "Agent %d: failed to parse response: %s", self.agent_id, e
            )
            return ActionType.DO_NOTHING, {}
