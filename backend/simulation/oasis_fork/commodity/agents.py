"""Factory functions for commodity market agents.

Usage:
    from oasis_fork.commodity.agents import make_coal_trader, make_bulk_shipper
    graph = AgentGraph()
    trader = make_coal_trader(agent_id=0, graph=graph, model=claude_model)
    graph.add_agent(trader)
"""

from ..social_agent.agent import SocialAgent
from ..social_agent.agent_graph import AgentGraph
from ..social_platform.config.user import CommodityAgentInfo
from ..social_platform.typing import ActionType

# Action sets per agent type
_TRADER_ACTIONS = [
    ActionType.SUBMIT_TRADE,
    ActionType.UPDATE_PRICE_VIEW,
    ActionType.CREATE_POST,
    ActionType.DO_NOTHING,
]

_SHIPPER_ACTIONS = [
    ActionType.REROUTE_VESSEL,
    ActionType.DO_NOTHING,
]

_GOVT_ACTIONS = [
    ActionType.IMPOSE_MEASURE,
    ActionType.ACTIVATE_INVENTORY,
    ActionType.CREATE_POST,
    ActionType.DO_NOTHING,
]

_REFINERY_ACTIONS = [
    ActionType.ACTIVATE_INVENTORY,
    ActionType.DO_NOTHING,
]


def make_coal_trader(
    agent_id: int,
    graph: AgentGraph,
    model,
    region: str = "JP",
    risk_tolerance: str = "medium",
) -> SocialAgent:
    """Create a coal commodity trader agent.

    Args:
        agent_id: Unique integer ID for the agent.
        graph: AgentGraph to register agent with.
        model: LLM model backend (e.g. ClaudeModel with Haiku).
        region: Operating region / importer country (e.g. 'JP', 'CN', 'KR', 'DE').
        risk_tolerance: 'low' | 'medium' | 'high'
    """
    profiles = {
        "JP": (
            "Procurement manager for Nippon Steel's coal supply. "
            "Buys 3M tonnes/month of thermal and coking coal. "
            "Primary sources: Newcastle (AU) 40%, Richards Bay (ZA) 25%, Kalimantan (ID) 35%."
        ),
        "CN": (
            "Coal trader for Shenhua Energy, China's largest coal importer. "
            "Opportunistic buyer, trades 8M tonnes/month across spot and forward markets. "
            "Has strategic reserve access."
        ),
        "KR": (
            "POSCO commodity desk, buying 2M tonnes/month for steel production. "
            "Risk-averse, prefers 60-day inventory buffer. "
            "Strong preference for Australian thermal coal quality."
        ),
        "DE": (
            "RWE Power AG procurement, buying thermal coal for power generation. "
            "Transitioning away from coal but needs short-term supply security. "
            "Watches API2 pricing."
        ),
    }
    description = profiles.get(
        region,
        f"Commodity trader in {region} market, buying coal for industrial use.",
    )

    inventory_days = {"low": 60, "medium": 45, "high": 30}.get(risk_tolerance, 45)

    agent = SocialAgent(
        agent_id=agent_id,
        user_info=CommodityAgentInfo(
            user_name=f"coal_trader_{region.lower()}_{agent_id}",
            agent_type="trader",
            commodity="coal",
            description=description,
            inventory_days=inventory_days,
            risk_tolerance=risk_tolerance,
            region=region,
        ),
        agent_graph=graph,
        model=model,
        available_actions=_TRADER_ACTIONS,
    )
    graph.add_agent(agent)
    return agent


def make_bulk_shipper(
    agent_id: int,
    graph: AgentGraph,
    model,
    vessel_count: int = 5,
) -> SocialAgent:
    """Create a bulk carrier shipping operator agent.

    Uses LLMAction but mostly responds to congestion data — low LLM cost.

    Args:
        agent_id: Unique integer ID.
        graph: AgentGraph to register agent with.
        model: LLM model backend.
        vessel_count: Number of vessels in operator's fleet.
    """
    agent = SocialAgent(
        agent_id=agent_id,
        user_info=CommodityAgentInfo(
            user_name=f"shipper_{agent_id}",
            agent_type="shipper",
            commodity="coal",
            description=(
                f"Capesize bulk carrier operator with {vessel_count} vessels on Pacific routes. "
                "Primary route: Newcastle (AU) to Japan/Korea. Will reroute to Richards Bay (ZA) "
                "or Kalimantan (ID) if Newcastle congestion index exceeds 8.0. "
                "Rerouting costs $450k per vessel in additional fuel and time."
            ),
            risk_tolerance="low",
            inventory_days=0,
        ),
        agent_graph=graph,
        model=model,
        available_actions=_SHIPPER_ACTIONS,
    )
    graph.add_agent(agent)
    return agent


def make_government_agent(
    agent_id: int,
    graph: AgentGraph,
    model,
    country: str = "AU",
) -> SocialAgent:
    """Create a government energy policy agent.

    Args:
        agent_id: Unique integer ID.
        graph: AgentGraph to register agent with.
        model: LLM model backend.
        country: Country code (e.g. 'AU', 'CN', 'JP', 'US', 'DE').
    """
    govt_profiles = {
        "AU": (
            "Australian Department of Resources. Manages coal export policy. "
            "Responds to domestic supply disruptions by adjusting export quotas "
            "and coordinating rail/port operators."
        ),
        "CN": (
            "China's National Development and Reform Commission (NDRC). "
            "Controls strategic coal reserves (90-day buffer). "
            "Can release reserves and adjust import quotas."
        ),
        "JP": (
            "Japan's Ministry of Economy, Trade and Industry (METI). "
            "Manages energy security. Can activate strategic petroleum reserve "
            "and negotiate emergency LNG contracts."
        ),
        "DE": (
            "German Federal Ministry for Economic Affairs. "
            "Manages emergency energy supply. Can invoke EU solidarity mechanism "
            "and release strategic reserves."
        ),
    }
    description = govt_profiles.get(
        country,
        f"Energy ministry of {country}, managing commodity supply security.",
    )

    agent = SocialAgent(
        agent_id=agent_id,
        user_info=CommodityAgentInfo(
            user_name=f"govt_{country.lower()}",
            agent_type="government",
            commodity="coal",
            description=description,
            risk_tolerance="low",
            region=country,
        ),
        agent_graph=graph,
        model=model,
        available_actions=_GOVT_ACTIONS,
    )
    graph.add_agent(agent)
    return agent


def make_refinery(
    agent_id: int,
    graph: AgentGraph,
    commodity: str = "coal",
    inventory_days: int = 30,
) -> SocialAgent:
    """Create a rule-based refinery/industrial buyer agent (no LLM cost).

    Uses ManualAction threshold logic — buy when inventory < threshold.
    Pass model=None and handle with ManualAction externally.

    Args:
        agent_id: Unique integer ID.
        graph: AgentGraph to register agent with.
        commodity: Primary commodity consumed.
        inventory_days: Current inventory buffer in days.
    """
    agent = SocialAgent(
        agent_id=agent_id,
        user_info=CommodityAgentInfo(
            user_name=f"refinery_{commodity}_{agent_id}",
            agent_type="refinery",
            commodity=commodity,
            description=(
                f"Industrial {commodity} consumer. Activates emergency inventory "
                "when buffer drops below 20 days."
            ),
            inventory_days=inventory_days,
            risk_tolerance="low",
        ),
        agent_graph=graph,
        model=None,
        available_actions=_REFINERY_ACTIONS,
    )
    graph.add_agent(agent)
    return agent
