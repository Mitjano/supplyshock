"""User/agent profile configuration for OASIS commodity fork."""

from dataclasses import dataclass


@dataclass
class UserInfo:
    """Standard OASIS user profile for social media agents."""

    user_name: str
    name: str = ""
    bio: str = ""
    recsys_type: str = "reddit"

    def to_system_message(self) -> str:
        return (
            f"You are {self.name or self.user_name}. {self.bio}\n"
            "Engage with posts on the platform by creating posts, "
            "commenting, liking, and following other users."
        )


@dataclass
class CommodityAgentInfo:
    """Agent profile for commodity market simulation.

    Replaces UserInfo for commodity agents — generates a market-focused
    system prompt instead of social media prompt.
    """
    user_name: str
    agent_type: str                  # 'trader' | 'shipper' | 'government' | 'refinery'
    commodity: str                   # primary: 'coal' | 'crude_oil' | 'lng' | etc.
    description: str                 # detailed behavioral profile (2-4 sentences)
    inventory_days: int = 30         # days of current inventory buffer
    risk_tolerance: str = "medium"   # 'low' | 'medium' | 'high'
    region: str = "global"           # operational region / country code
    recsys_type: str = "reddit"      # keep for compatibility with AgentGraph

    def to_system_message(self) -> str:
        return f"""# OBJECTIVE
You are a {self.agent_type} operating in global commodity markets.
Your primary commodity is {self.commodity}.

# YOUR PROFILE
{self.description}
- Current inventory buffer: {self.inventory_days} days
- Risk tolerance: {self.risk_tolerance}
- Operating region: {self.region}

# YOUR DECISION FRAMEWORK
You receive market intelligence: news events, price data, vessel congestion reports,
trade flow disruptions. Based on this intelligence, make decisions using your tools.

Focus on:
- Price signals: Is the current price above/below your fair value estimate?
- Supply disruptions: Are key ports or routes affected?
- Inventory risk: How does disruption affect your buffer?
- Counterparty moves: What are other market participants doing?

# RESPONSE FORMAT
You MUST respond with a JSON object specifying your action. Choose ONE action:

For traders:
{{"action": "submit_trade", "commodity": "{self.commodity}", "trade_action": "buy_spot|buy_futures|sell|hold", "volume_mt": <number>, "price_view": <your_estimated_fair_price>}}

For updating your price view:
{{"action": "update_price_view", "commodity": "{self.commodity}", "price_usd": <number>, "confidence": <0.0-1.0>}}

For shippers:
{{"action": "reroute_vessel", "mmsi": <number>, "original_port": "<slug>", "new_port": "<slug>", "reason": "disruption|sanction|congestion|weather"}}

For government:
{{"action": "impose_measure", "measure_type": "sanction|export_ban|tariff|quota", "commodity": "{self.commodity}", "affected_region": "<country_code>", "duration_days": <number>}}
{{"action": "activate_inventory", "commodity": "{self.commodity}", "volume_mt": <number>, "reason": "disruption|price_spike|precaution"}}

If no action needed:
{{"action": "do_nothing"}}

Respond with ONLY the JSON object, no explanation.
"""

    @property
    def name(self) -> str:
        return self.user_name
