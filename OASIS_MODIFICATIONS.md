# OASIS Commodity Fork — Dokumentacja techniczna
# SupplyShock — backend/simulation/oasis_fork/
#
# Ten dokument opisuje WSZYSTKIE modyfikacje względem upstream OASIS (camel-ai/oasis).
# Czytaj przed implementacją Issue #26.
#
# Upstream: https://github.com/camel-ai/oasis
# Wersja bazowa: camel-oasis PyPI (Python <3.12 ≥3.10 — uwaga: wymaga venv z Python 3.11)

---

## Dlaczego fork, nie pip install

OASIS PyPI (`camel-oasis`) nie obsługuje Python 3.12. Projekt używa 3.12. Rozwiązanie:
1. Skopiuj kod źródłowy OASIS do `backend/simulation/oasis_fork/`
2. Modyfikuj lokalną kopię
3. W `engine.py` importuj z `oasis_fork`, nie z zainstalowanego pakietu

Alternatywa: `pyenv` z Python 3.11 w osobnym virtualenv dla symulacji.

---

## Mapa zmian — pełna lista

### MODYFIKACJE (istniejące pliki)

#### `oasis/social_platform/typing.py` — ActionType + DefaultPlatformType

Dodaj do klasy `ActionType` po istniejących wartościach:

```python
# ── Commodity actions (SupplyShock fork) ─────────────────────
SUBMIT_TRADE       = "submit_trade"        # trader: buy/sell/hold commodity
REROUTE_VESSEL     = "reroute_vessel"      # shipper: zmień port docelowy
UPDATE_PRICE_VIEW  = "update_price_view"   # trader: zaktualizuj szacunek ceny
IMPOSE_MEASURE     = "impose_measure"      # rząd: sankcja, embargo, taryfa
ACTIVATE_INVENTORY = "activate_inventory"  # buyer: uruchom zapasy strategiczne
```

Dodaj do klasy `DefaultPlatformType`:
```python
COMMODITY = "commodity"
```

---

#### `oasis/environment/env.py` — OasisEnv.__init__

W bloku `if isinstance(platform, DefaultPlatformType):`, po bloku `elif platform == DefaultPlatformType.REDDIT:`, dodaj:

```python
elif platform == DefaultPlatformType.COMMODITY:
    self.channel = Channel()
    self.platform = Platform(
        db_path=database_path,
        channel=self.channel,
        recsys_type="reddit",        # market board uses reddit-style rec sys
        max_rec_post_len=50,         # więcej eventów w "feedzie rynkowym"
        refresh_rec_post_count=10,   # agent widzi więcej market intelligence
        allow_self_rating=True,
        show_score=False,
    )
    self.platform_type = DefaultPlatformType.COMMODITY
```

---

#### `oasis/social_platform/platform.py` — 5 nowych async handlers

**KRYTYCZNA REGUŁA:** Platform.running() ma hardcoded check `if len_param_names > 3: raise ValueError`.
Każda metoda może mieć max 3 parametry: `self`, `agent_id`, jeden parametr z danymi.
Używaj tuple do pakowania wielu wartości.

Dodaj po metodzie `do_nothing()` (linia ~1332):

```python
async def submit_trade(self, agent_id: int, trade_message: tuple):
    """Record a commodity trade decision by an agent.

    trade_message tuple: (commodity, action, volume_mt, price_view)
    - commodity: str — 'coal', 'crude_oil', 'lng', 'iron_ore', etc.
    - action: str — 'buy_spot', 'buy_futures', 'sell', 'hold'
    - volume_mt: float — volume in metric tonnes
    - price_view: float — agent's estimated fair price USD/unit
    """
    commodity, action, volume_mt, price_view = trade_message
    current_time = datetime.now()
    try:
        self.db_cursor.execute(
            "INSERT INTO trade (agent_id, commodity, action, "
            "volume_mt, price_view, created_at) VALUES (?,?,?,?,?,?)",
            (agent_id, commodity, action, volume_mt, price_view, current_time)
        )
        self.db.commit()
        self.pl_utils._record_trace(
            agent_id, ActionType.SUBMIT_TRADE.value,
            {"commodity": commodity, "action": action,
             "volume_mt": volume_mt, "price_view": price_view},
            current_time
        )
        return {"success": True, "trade_id": self.db_cursor.lastrowid}
    except Exception as e:
        twitter_log.error(f"submit_trade error agent {agent_id}: {e}")
        return {"success": False, "error": str(e)}


async def reroute_vessel(self, agent_id: int, reroute_message: tuple):
    """Shipper diverts vessel to alternative port due to disruption.

    reroute_message tuple: (mmsi, original_port, new_port, reason)
    - mmsi: int — vessel MMSI identifier
    - original_port: str — original destination port slug
    - new_port: str — new destination port slug
    - reason: str — 'disruption', 'sanction', 'congestion', 'weather'
    """
    mmsi, original_port, new_port, reason = reroute_message
    current_time = datetime.now()
    try:
        self.db_cursor.execute(
            "INSERT INTO vessel_decision (agent_id, mmsi, original_port, "
            "new_port, reason, created_at) VALUES (?,?,?,?,?,?)",
            (agent_id, mmsi, original_port, new_port, reason, current_time)
        )
        self.db.commit()
        self.pl_utils._record_trace(
            agent_id, ActionType.REROUTE_VESSEL.value,
            {"mmsi": mmsi, "from": original_port, "to": new_port,
             "reason": reason},
            current_time
        )
        return {"success": True, "new_port": new_port}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def update_price_view(self, agent_id: int, price_message: tuple):
    """Trader records updated price estimate for commodity.

    price_message tuple: (commodity, price_usd, confidence)
    - commodity: str
    - price_usd: float — estimated fair price
    - confidence: float — 0.0 to 1.0
    """
    commodity, price_usd, confidence = price_message
    current_time = datetime.now()
    try:
        self.db_cursor.execute(
            "INSERT INTO market_state (commodity, agent_id, price_view, "
            "confidence, created_at) VALUES (?,?,?,?,?)",
            (commodity, agent_id, price_usd, confidence, current_time)
        )
        self.db.commit()
        self.pl_utils._record_trace(
            agent_id, ActionType.UPDATE_PRICE_VIEW.value,
            {"commodity": commodity, "price_view": price_usd,
             "confidence": confidence},
            current_time
        )
        return {"success": True, "recorded_price": price_usd}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def impose_measure(self, agent_id: int, measure_message: tuple):
    """Government agent imposes trade measure on commodity flow.

    measure_message tuple: (measure_type, commodity, affected_region, duration_days)
    - measure_type: str — 'sanction', 'export_ban', 'tariff', 'quota'
    - commodity: str
    - affected_region: str — country code e.g. 'RU', 'AU'
    - duration_days: int
    """
    measure_type, commodity, affected_region, duration_days = measure_message
    current_time = datetime.now()
    self.pl_utils._record_trace(
        agent_id, ActionType.IMPOSE_MEASURE.value,
        {"type": measure_type, "commodity": commodity,
         "region": affected_region, "duration_days": duration_days},
        current_time
    )
    return {"success": True, "measure": measure_type}


async def activate_inventory(self, agent_id: int, inventory_message: tuple):
    """Buyer activates strategic inventory / emergency stock.

    inventory_message tuple: (commodity, volume_mt, reason)
    - commodity: str
    - volume_mt: float — volume released from strategic reserves
    - reason: str — 'disruption', 'price_spike', 'precaution'
    """
    commodity, volume_mt, reason = inventory_message
    current_time = datetime.now()
    self.pl_utils._record_trace(
        agent_id, ActionType.ACTIVATE_INVENTORY.value,
        {"commodity": commodity, "volume_mt": volume_mt, "reason": reason},
        current_time
    )
    return {"success": True, "released_mt": volume_mt}
```

---

#### `oasis/social_platform/database.py` — ładowanie commodity schemas

W funkcji `create_db()`, po ostatnim istniejącym schema block (group_message), dodaj:

```python
# Commodity extension tables (SupplyShock fork)
# Graceful — nie crashuje jeśli pliki nie istnieją (np. w testach OASIS)
for schema_file in ["trade.sql", "market_state.sql", "vessel_decision.sql"]:
    schema_path = osp.join(schema_dir, schema_file)
    if osp.exists(schema_path):
        with open(schema_path, "r") as sql_file:
            cursor.executescript(sql_file.read())
```

---

#### `oasis/social_platform/config/user.py` — CommodityAgentInfo

Dodaj po klasie `UserInfo`:

```python
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

# RESPONSE METHOD
Execute decisions by calling the available tools. Always specify commodity,
volume, and your price estimate. Be specific — avoid "I might consider" language.
"""

    # Compatibility shim — OASIS agents_generator expects user_info.recsys_type
    @property
    def name(self) -> str:
        return self.user_name
```

---

#### `oasis/social_agent/agent.py` — routing do CommodityEnvironment

Zmień linie 74–83 (sekcja tworzenia `self.env` i `system_message_content`):

```python
# PRZED (oryginał):
self.env = SocialEnvironment(SocialAction(agent_id, self.channel))
if user_info_template is None:
    system_message_content = self.user_info.to_system_message()
else:
    system_message_content = self.user_info.to_custom_system_message(user_info_template)

# PO (fork):
from oasis.social_agent.agent_environment import SocialEnvironment, CommodityEnvironment
from oasis.social_platform.config.user import CommodityAgentInfo

action = SocialAction(agent_id, self.channel)
if isinstance(user_info, CommodityAgentInfo):
    self.env = CommodityEnvironment(action)
    system_message_content = user_info.to_system_message()
elif user_info_template is None:
    self.env = SocialEnvironment(action)
    system_message_content = self.user_info.to_system_message()
else:
    self.env = SocialEnvironment(action)
    system_message_content = self.user_info.to_custom_system_message(user_info_template)
```

---

#### `oasis/social_agent/agent_environment.py` — CommodityEnvironment

Dodaj po klasie `SocialEnvironment`:

```python
class CommodityEnvironment(SocialEnvironment):
    """Environment observation for commodity market agents.

    Overrides to_text_prompt() to present market intelligence instead
    of social media feed framing.
    """

    market_env_template = Template(
        "## CURRENT MARKET INTELLIGENCE\n"
        "$market_events\n\n"
        "## MARKET CONSENSUS\n"
        "$market_state\n\n"
        "Based on this intelligence, decide your next action. "
        "Use your tools to execute trades, update price views, or respond to disruptions."
    )

    async def to_text_prompt(
        self,
        include_posts: bool = True,
        include_followers: bool = False,
        include_follows: bool = False,
    ) -> str:
        """Generate market-focused observation string for the agent."""
        # Fetch "posts" from OASIS — these are market events seeded by ManualAction
        if include_posts:
            posts = await self.action.refresh()
            if posts.get("success") and posts.get("posts"):
                events = []
                for p in posts["posts"]:
                    content = p.get("content", "")
                    if content:
                        events.append(f"[EVENT] {content}")
                market_events = "\n".join(events) if events else "No new market events."
            else:
                market_events = "No new market events."
        else:
            market_events = "Market feed disabled."

        market_state = await self._get_market_state()

        return self.market_env_template.substitute(
            market_events=market_events,
            market_state=market_state,
        )

    async def _get_market_state(self) -> str:
        """Read current price consensus from market_state table."""
        try:
            db_path = get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT commodity,
                       ROUND(AVG(price_view), 2) as avg_price,
                       COUNT(*) as num_views,
                       ROUND(AVG(confidence), 2) as avg_confidence
                FROM market_state
                WHERE created_at > datetime('now', '-1 hour')
                GROUP BY commodity
                ORDER BY num_views DESC
                LIMIT 10
            """)
            rows = cursor.fetchall()
            conn.close()
            if not rows:
                return "No price consensus established yet."
            lines = [
                f"{r[0]}: ${r[1]}/unit "
                f"(consensus from {r[2]} agents, confidence {r[3]:.0%})"
                for r in rows
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"Market state unavailable: {e}"
```

---

### NOWE PLIKI

#### `oasis/social_platform/schema/trade.sql`

```sql
-- SupplyShock commodity fork — trade decisions table
CREATE TABLE IF NOT EXISTS trade (
    trade_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id   INTEGER NOT NULL,
    commodity  TEXT NOT NULL,
    action     TEXT NOT NULL,
    volume_mt  REAL DEFAULT 0,
    price_view REAL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY(agent_id) REFERENCES user(user_id)
);
CREATE INDEX IF NOT EXISTS idx_trade_commodity ON trade(commodity);
CREATE INDEX IF NOT EXISTS idx_trade_agent ON trade(agent_id);
```

#### `oasis/social_platform/schema/market_state.sql`

```sql
-- SupplyShock commodity fork — price consensus per timestep
CREATE TABLE IF NOT EXISTS market_state (
    state_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    commodity  TEXT NOT NULL,
    agent_id   INTEGER,
    price_view REAL NOT NULL,
    confidence REAL DEFAULT 1.0,
    timestep   INTEGER DEFAULT 0,
    created_at DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ms_commodity ON market_state(commodity, created_at);
```

#### `oasis/social_platform/schema/vessel_decision.sql`

```sql
-- SupplyShock commodity fork — vessel rerouting decisions
CREATE TABLE IF NOT EXISTS vessel_decision (
    decision_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id      INTEGER NOT NULL,
    mmsi          INTEGER,
    original_port TEXT,
    new_port      TEXT,
    reason        TEXT,
    created_at    DATETIME NOT NULL,
    FOREIGN KEY(agent_id) REFERENCES user(user_id)
);
```

---

#### `oasis/commodity/__init__.py`

```python
# SupplyShock OASIS commodity fork
from oasis.commodity.toolkits import COMMODITY_TOOLS, get_commodity_price, get_port_congestion, get_trade_flow
from oasis.commodity.agents import make_coal_trader, make_bulk_shipper, make_government_agent
from oasis.commodity.market import compute_consensus_price

__all__ = [
    "COMMODITY_TOOLS",
    "get_commodity_price", "get_port_congestion", "get_trade_flow",
    "make_coal_trader", "make_bulk_shipper", "make_government_agent",
    "compute_consensus_price",
]
```

---

#### `oasis/commodity/toolkits.py`

```python
"""Commodity market FunctionTools for OASIS agents.

All functions must have complete docstrings with Args and Returns sections.
CAMEL FunctionTool builds tool schema from docstring — missing sections = error.
"""
import os
import sqlite3
from typing import Optional
from camel.toolkits import FunctionTool


# In production: reads from TimescaleDB (SUPPLYSHOCK_DB_URL)
# In POC/dev: returns hardcoded baseline values
_BASELINE_PRICES = {
    "coal":      {"price_usd": 118.40, "unit": "tonne",  "benchmark": "API2_Newcastle"},
    "crude_oil": {"price_usd": 74.20,  "unit": "barrel", "benchmark": "Brent_ICE"},
    "lng":       {"price_usd": 12.80,  "unit": "mmbtu",  "benchmark": "TTF_Europe"},
    "iron_ore":  {"price_usd": 103.50, "unit": "tonne",  "benchmark": "TSI_62pct_CFR"},
    "copper":    {"price_usd": 9240.0, "unit": "tonne",  "benchmark": "LME_Copper"},
    "wheat":     {"price_usd": 192.00, "unit": "tonne",  "benchmark": "CBOT_Wheat"},
}

_PORT_STATUS = {
    "port_newcastle_au": {"vessel_count": 47, "congestion_index": 9.2,
                          "risk_level": "critical", "disruption_active": True},
    "port_richards_bay_za": {"vessel_count": 12, "congestion_index": 2.1,
                              "risk_level": "normal", "disruption_active": False},
    "strait_hormuz": {"vessel_count": 234, "congestion_index": 3.5,
                      "risk_level": "elevated", "disruption_active": False},
    "suez_canal": {"vessel_count": 89, "congestion_index": 4.1,
                   "risk_level": "elevated", "disruption_active": False},
}


def get_commodity_price(commodity: str) -> dict:
    """Get current spot price for a commodity from market data.

    Args:
        commodity: Commodity identifier. One of: coal, crude_oil, lng,
            iron_ore, copper, wheat, aluminium, nickel, soybeans, palladium.

    Returns:
        dict: Contains keys: price_usd (float), unit (str), benchmark (str),
            change_1d_pct (float), is_delayed (bool). Returns error key if
            commodity not found.
    """
    if commodity not in _BASELINE_PRICES:
        return {"error": f"Unknown commodity: {commodity}. Valid: {list(_BASELINE_PRICES.keys())}"}
    data = dict(_BASELINE_PRICES[commodity])
    data["change_1d_pct"] = 0.0
    data["is_delayed"] = True
    return data


def get_port_congestion(port_slug: str) -> dict:
    """Get current vessel congestion at a port or maritime chokepoint.

    Args:
        port_slug: Port or chokepoint identifier. Examples:
            'port_newcastle_au', 'port_richards_bay_za', 'strait_hormuz',
            'suez_canal', 'strait_malacca', 'strait_bosporus'.

    Returns:
        dict: Contains keys: vessel_count (int), congestion_index (float, 0-10),
            risk_level (str: normal/elevated/high/critical),
            disruption_active (bool). Returns error key if slug not found.
    """
    if port_slug not in _PORT_STATUS:
        return {"vessel_count": 0, "congestion_index": 0.0,
                "risk_level": "unknown", "disruption_active": False,
                "note": f"No data for {port_slug}"}
    return dict(_PORT_STATUS[port_slug])


def get_trade_flow(commodity: str, origin: str, destination: str) -> dict:
    """Get monthly trade flow volume between two regions for a commodity.

    Args:
        commodity: Commodity type (coal, crude_oil, lng, iron_ore, etc.)
        origin: Exporting country ISO code (e.g. 'AU', 'SA', 'RU', 'ID', 'US')
        destination: Importing country ISO code (e.g. 'JP', 'CN', 'DE', 'KR')

    Returns:
        dict: Contains keys: volume_mt_monthly (float), value_usd_monthly (float),
            alternative_sources (list of country codes), dependency_pct (float,
            how dependent destination is on this origin for this commodity).
    """
    # POC: simplified lookup
    key = (commodity, origin, destination)
    flows = {
        ("coal", "AU", "JP"): {"volume_mt_monthly": 3_200_000, "value_usd_monthly": 378_880_000,
                                "alternative_sources": ["ZA", "CO", "ID"],
                                "dependency_pct": 0.38},
        ("coal", "AU", "CN"): {"volume_mt_monthly": 5_100_000, "value_usd_monthly": 603_840_000,
                                "alternative_sources": ["ID", "MN", "RU"],
                                "dependency_pct": 0.18},
        ("crude_oil", "SA", "JP"): {"volume_mt_monthly": 4_800_000, "value_usd_monthly": 1_751_040_000,
                                     "alternative_sources": ["AE", "KW", "IQ"],
                                     "dependency_pct": 0.42},
    }
    result = flows.get(key, {
        "volume_mt_monthly": 0,
        "value_usd_monthly": 0,
        "alternative_sources": [],
        "dependency_pct": 0.0,
        "note": f"No flow data for {commodity} {origin}→{destination}"
    })
    return dict(result)


def get_current_simulation_step() -> dict:
    """Get current simulation timestep and simulated date.

    Returns:
        dict: Contains keys: timestep (int), simulated_date (str ISO format),
            days_since_event (int, days since seed disruption event).
    """
    # Platform-injected — simulation engine sets this
    sim_step = int(os.environ.get("OASIS_SIM_STEP", "0"))
    return {
        "timestep": sim_step,
        "simulated_date": f"T+{sim_step * 7} days",  # 1 step = 1 week
        "days_since_event": sim_step * 7,
    }


# Ready-to-use tool lists for SocialAgent(tools=[...])
COMMODITY_TOOLS = [
    FunctionTool(get_commodity_price),
    FunctionTool(get_port_congestion),
    FunctionTool(get_trade_flow),
    FunctionTool(get_current_simulation_step),
]

TRADER_TOOLS = COMMODITY_TOOLS  # all tools

SHIPPER_TOOLS = [
    FunctionTool(get_port_congestion),
    FunctionTool(get_current_simulation_step),
]

GOVERNMENT_TOOLS = COMMODITY_TOOLS  # all tools
```

---

#### `oasis/commodity/agents.py`

```python
"""Factory functions for commodity market agents.

Usage:
    from oasis.commodity.agents import make_coal_trader, make_bulk_shipper
    graph = AgentGraph()
    trader = make_coal_trader(agent_id=0, graph=graph, model=haiku_model)
    graph.add_agent(trader)
"""
from camel.toolkits import FunctionTool
from oasis import AgentGraph, ActionType
from oasis.social_agent.agent import SocialAgent
from oasis.social_platform.config.user import CommodityAgentInfo
from oasis.commodity.toolkits import (
    TRADER_TOOLS, SHIPPER_TOOLS, GOVERNMENT_TOOLS, get_port_congestion
)

# Action sets per agent type
_TRADER_ACTIONS = [
    ActionType.SUBMIT_TRADE,
    ActionType.UPDATE_PRICE_VIEW,
    ActionType.CREATE_POST,    # agent może "ogłosić" swój price view
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


def make_coal_trader(agent_id: int, graph: AgentGraph, model,
                     region: str = "JP", risk_tolerance: str = "medium") -> SocialAgent:
    """Create a coal commodity trader agent.

    Args:
        agent_id: Unique integer ID for the agent.
        graph: AgentGraph to add agent to.
        model: CAMEL model backend (e.g. Claude Haiku).
        region: Operating region / importer country (e.g. 'JP', 'CN', 'KR', 'DE').
        risk_tolerance: 'low' | 'medium' | 'high'
    """
    profiles = {
        "JP": "Procurement manager for Nippon Steel's coal supply. Buys 3M tonnes/month of thermal and coking coal. Primary sources: Newcastle (AU) 40%, Richards Bay (ZA) 25%, Kalimantan (ID) 35%.",
        "CN": "Coal trader for Shenhua Energy, China's largest coal importer. Opportunistic buyer, trades 8M tonnes/month across spot and forward markets. Has strategic reserve access.",
        "KR": "POSCO commodity desk, buying 2M tonnes/month for steel production. Risk-averse, prefers 60-day inventory buffer. Strong preference for Australian thermal coal quality.",
        "DE": "RWE Power AG procurement, buying thermal coal for power generation. Transitioning away from coal but needs short-term supply security. Watches API2 pricing.",
    }
    description = profiles.get(region,
        f"Commodity trader in {region} market, buying coal for industrial use.")

    return SocialAgent(
        agent_id=agent_id,
        user_info=CommodityAgentInfo(
            user_name=f"coal_trader_{region.lower()}_{agent_id}",
            agent_type="trader",
            commodity="coal",
            description=description,
            inventory_days=45 if risk_tolerance == "medium" else (60 if risk_tolerance == "low" else 30),
            risk_tolerance=risk_tolerance,
            region=region,
        ),
        tools=TRADER_TOOLS,
        agent_graph=graph,
        model=model,
        available_actions=_TRADER_ACTIONS,
    )


def make_bulk_shipper(agent_id: int, graph: AgentGraph, model,
                      vessel_count: int = 5) -> SocialAgent:
    """Create a bulk carrier shipping operator agent.

    Uses LLMAction but mostly responds to congestion data — low LLM cost.

    Args:
        vessel_count: Number of vessels in operator's fleet.
    """
    return SocialAgent(
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
            inventory_days=0,  # shippers don't hold inventory
        ),
        tools=SHIPPER_TOOLS,
        agent_graph=graph,
        model=model,
        available_actions=_SHIPPER_ACTIONS,
    )


def make_government_agent(agent_id: int, graph: AgentGraph, model,
                           country: str = "AU") -> SocialAgent:
    """Create a government energy policy agent.

    Args:
        country: Country code (e.g. 'AU', 'CN', 'JP', 'US', 'DE').
    """
    govt_profiles = {
        "AU": "Australian Department of Resources. Manages coal export policy. Responds to domestic supply disruptions by adjusting export quotas and coordinating rail/port operators.",
        "CN": "China's National Development and Reform Commission (NDRC). Controls strategic coal reserves (90-day buffer). Can release reserves and adjust import quotas.",
        "JP": "Japan's Ministry of Economy, Trade and Industry (METI). Manages energy security. Can activate strategic petroleum reserve and negotiate emergency LNG contracts.",
        "DE": "German Federal Ministry for Economic Affairs. Manages emergency energy supply. Can invoke EU solidarity mechanism and release strategic reserves.",
    }
    description = govt_profiles.get(country,
        f"Energy ministry of {country}, managing commodity supply security.")

    return SocialAgent(
        agent_id=agent_id,
        user_info=CommodityAgentInfo(
            user_name=f"govt_{country.lower()}",
            agent_type="government",
            commodity="coal",
            description=description,
            risk_tolerance="low",
            region=country,
        ),
        tools=GOVERNMENT_TOOLS,
        agent_graph=graph,
        model=model,
        available_actions=_GOVT_ACTIONS,
    )


def make_refinery(agent_id: int, graph: AgentGraph,
                  commodity: str = "coal", inventory_days: int = 30) -> SocialAgent:
    """Create a rule-based refinery/industrial buyer agent (no LLM cost).

    Uses ManualAction threshold logic — buy when inventory < threshold.
    Pass model=None and handle with ManualAction externally.
    """
    return SocialAgent(
        agent_id=agent_id,
        user_info=CommodityAgentInfo(
            user_name=f"refinery_{commodity}_{agent_id}",
            agent_type="refinery",
            commodity=commodity,
            description=f"Industrial {commodity} consumer. Activates emergency inventory when buffer drops below 20 days.",
            inventory_days=inventory_days,
            risk_tolerance="low",
        ),
        tools=[],
        agent_graph=graph,
        model=None,  # rule-based — no LLM
        available_actions=_REFINERY_ACTIONS,
    )
```

---

#### `oasis/commodity/market.py`

```python
"""Price discovery utilities for commodity simulation.

Aggregates agent price views from market_state table
to compute the emergent market consensus price.
"""
import sqlite3
from typing import Optional


def compute_consensus_price(commodity: str, db_path: str,
                             last_n_steps: int = 1) -> Optional[float]:
    """Compute consensus market price from agent price views.

    Aggregates AVG(price_view) from market_state table filtered by
    recent timesteps. This is the emergent market price — not set by
    the simulation, but discovered through agent decisions.

    Args:
        commodity: Commodity to aggregate (coal, crude_oil, etc.)
        db_path: Path to OASIS SQLite database.
        last_n_steps: Number of recent timesteps to include.

    Returns:
        float: Weighted average price view, or None if no data.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                ROUND(SUM(price_view * confidence) / SUM(confidence), 2) as weighted_avg,
                COUNT(*) as num_views,
                MIN(price_view) as low,
                MAX(price_view) as high
            FROM market_state
            WHERE commodity = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (commodity, last_n_steps * 100))
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return float(row[0])
        return None
    except Exception:
        return None


def get_simulation_summary(db_path: str) -> dict:
    """Generate post-simulation summary from SQLite database.

    Used by ReportAgent to build narrative PDF report.

    Args:
        db_path: Path to OASIS SQLite database.

    Returns:
        dict with keys: trade_counts, price_evolution, reroutes, measures.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Trade action distribution
    cursor.execute("""
        SELECT commodity, action, COUNT(*) as n, AVG(price_view) as avg_price
        FROM trade GROUP BY commodity, action ORDER BY n DESC
    """)
    trade_counts = [
        {"commodity": r[0], "action": r[1], "count": r[2], "avg_price": r[3]}
        for r in cursor.fetchall()
    ]

    # Price evolution over time
    cursor.execute("""
        SELECT commodity, ROUND(AVG(price_view), 2) as avg_price, created_at
        FROM market_state GROUP BY commodity, DATE(created_at)
        ORDER BY created_at
    """)
    price_evolution = [
        {"commodity": r[0], "price": r[1], "at": r[2]}
        for r in cursor.fetchall()
    ]

    # Vessel reroutes
    cursor.execute("SELECT new_port, reason, COUNT(*) as n FROM vessel_decision GROUP BY new_port, reason")
    reroutes = [{"port": r[0], "reason": r[1], "count": r[2]} for r in cursor.fetchall()]

    # Government measures
    cursor.execute("SELECT info FROM trace WHERE action = 'impose_measure'")
    measures = [r[0] for r in cursor.fetchall()]

    conn.close()
    return {
        "trade_counts": trade_counts,
        "price_evolution": price_evolution,
        "reroutes": reroutes,
        "measures": measures,
    }
```

---

## POC script — `backend/simulation/poc_newcastle.py`

```python
"""
OASIS Commodity Fork — Newcastle Flood POC

Tests that the commodity fork produces sensible economic behavior
for a coal supply disruption scenario.

Run: python poc_newcastle.py
Expected: < 3 min, < $0.50 LLM cost, ≥60% agents react with buy action.
"""
import asyncio
import os
import sqlite3

# Adjust path for local fork
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType

from oasis_fork import ActionType, AgentGraph, LLMAction, ManualAction
from oasis_fork.environment.env import OasisEnv
from oasis_fork.social_platform.typing import DefaultPlatformType
from oasis_fork.commodity.agents import make_coal_trader, make_government_agent
from oasis_fork.commodity.market import compute_consensus_price, get_simulation_summary

DB_PATH = "/tmp/poc_newcastle.db"


async def main():
    # Clean previous run
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # Model: Claude Haiku — cheapest capable model
    haiku = ModelFactory.create(
        model_platform=ModelPlatformType.ANTHROPIC,
        model_type=ModelType.CLAUDE_HAIKU_3_5,  # adjust to available model
    )

    graph = AgentGraph()

    # 10 LLM traders (different regions)
    regions = ["JP", "JP", "JP", "CN", "CN", "KR", "KR", "DE", "JP", "CN"]
    for i, region in enumerate(regions):
        agent = make_coal_trader(i, graph, haiku, region=region)
        graph.add_agent(agent)

    # 1 government agent (Australia — source country)
    govt = make_government_agent(10, graph, haiku, country="AU")
    graph.add_agent(govt)

    # 89 rule-based shippers (ManualAction DO_NOTHING — zero LLM cost)
    from oasis_fork.social_platform.config.user import CommodityAgentInfo
    from oasis_fork.social_agent.agent import SocialAgent
    for i in range(11, 100):
        shipper = SocialAgent(
            agent_id=i,
            user_info=CommodityAgentInfo(
                user_name=f"shipper_{i}",
                agent_type="shipper",
                commodity="coal",
                description="Bulk carrier operator, Newcastle to Japan route.",
            ),
            tools=[],
            agent_graph=graph,
            model=haiku,
            available_actions=[ActionType.DO_NOTHING],
        )
        graph.add_agent(shipper)

    # Initialize environment with COMMODITY platform
    env = OasisEnv(
        agent_graph=graph,
        platform=DefaultPlatformType.COMMODITY,
        database_path=DB_PATH,
        semaphore=10,  # limit concurrent LLM calls
    )

    await env.reset()
    print("Environment initialized.")

    # STEP 0: Inject disruption seed event
    system_agent = env.agent_graph.get_agent(0)
    seed_content = (
        "BREAKING MARKET ALERT: Hunter Valley Railway (NSW, Australia) flooded "
        "due to extreme rainfall. All coal train services suspended. "
        "Port of Newcastle throughput down 85% — from 13M t/month to ~2M t/month. "
        "Estimated disruption: 3 weeks minimum. "
        "API2 Newcastle spot cargo: 11M tonne monthly deficit entering market. "
        "Current spot price: $118.40/t (API2). "
        "Richards Bay (ZA) and Kalimantan (ID) alternative origins available "
        "but at 8-12 day longer voyage time."
    )
    await env.step({
        system_agent: ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": seed_content}
        )
    })
    print("Seed event injected.")

    # STEPS 1-5: LLM agents react, rule-based agents do nothing
    llm_agents = list(env.agent_graph.get_agents())[:11]  # traders + govt
    rule_agents = list(env.agent_graph.get_agents())[11:]

    for step in range(1, 6):
        os.environ["OASIS_SIM_STEP"] = str(step)
        print(f"Step {step}/5...")

        actions = {}
        # LLM decisions
        for _, agent in llm_agents:
            actions[agent] = LLMAction()
        # Rule-based: do nothing
        for _, agent in rule_agents:
            actions[agent] = ManualAction(
                action_type=ActionType.DO_NOTHING,
                action_args={}
            )
        await env.step(actions)

    await env.close()

    # ── RESULTS ──────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("POC RESULTS — Newcastle Flood Simulation")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Trade actions
    cursor.execute("SELECT action, COUNT(*) FROM trade GROUP BY action")
    trades = cursor.fetchall()
    total_trades = sum(t[1] for t in trades)
    buy_trades = sum(t[1] for t in trades if "buy" in t[0])
    print(f"\nTrade decisions: {total_trades} total")
    for action, count in trades:
        print(f"  {action}: {count}")

    # Price evolution
    consensus = compute_consensus_price("coal", DB_PATH)
    print(f"\nConsensus price: ${consensus:.2f}/t" if consensus else "\nNo consensus price recorded.")
    print(f"Baseline price: $118.40/t")
    if consensus:
        pct_change = (consensus - 118.40) / 118.40 * 100
        print(f"Price change: {pct_change:+.1f}%")

    # Vessel reroutes
    cursor.execute("SELECT COUNT(*) FROM vessel_decision WHERE new_port != original_port")
    reroutes = cursor.fetchone()[0]
    print(f"\nVessel reroutes: {reroutes}")

    conn.close()

    # Pass/fail criteria
    print("\n── ACCEPTANCE CRITERIA ──")
    checks = [
        ("≥60% LLM agents react with buy", buy_trades >= 6,
         f"{buy_trades}/10 LLM agents bought"),
        ("Consensus price > baseline", consensus and consensus > 118.40,
         f"${consensus:.2f}" if consensus else "no data"),
        ("Total trades > 0", total_trades > 0, f"{total_trades} trades"),
        ("Heterogeneous reactions", len(trades) >= 2, f"{len(trades)} distinct actions"),
    ]
    passed = 0
    for label, result, detail in checks:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {label} ({detail})")
        if result:
            passed += 1
    print(f"\n{passed}/{len(checks)} criteria passed")
    if passed < len(checks):
        print("→ Debug: check agent descriptions in make_coal_trader()")
        print("→ Check: seed event content is visible in agent feed")
        print("→ Try: increase max_rec_post_len in DefaultPlatformType.COMMODITY")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## ## Zmienne środowiskowe wymagane przez oasis_fork

| Zmienna | Gdzie używana | Wartość dev |
|---------|--------------|-------------|
| `SUPPLYSHOCK_DB_URL` | `commodity/toolkits.py` — TimescaleDB live data | `postgresql://supplyshock:supplyshock_dev@db:5432/supplyshock` |
| `OASIS_DB_PATH` | `database.py` — lokalizacja SQLite per symulacja | `/tmp/simulation_{job_id}.db` |
| `OASIS_SIM_STEP` | `toolkits.py` — krok symulacji (inject przez engine.py) | `0` |
| `ANTHROPIC_API_KEY` | CAMEL/OASIS dla LLM agentów | z `.env` |

Architektura danych: OASIS używa SQLite per symulacja (izolacja). TimescaleDB jest czytany przez toolkits jako źródło live danych rynkowych. Po zakończeniu symulacji `get_simulation_summary()` eksportuje wyniki do TimescaleDB przez SupplyShock backend.

---

Znane ograniczenia upstream OASIS do świadomości

1. **Python <3.12** — PyPI package nie instaluje się na Python 3.12. Używaj lokalnego forka lub pyenv z 3.11.

2. **SQLite, nie PostgreSQL** — OASIS używa SQLite dla symulacji. To jest OK dla POC. W produkcji możesz czytać wyniki z SQLite i zapisywać do TimescaleDB po zakończeniu symulacji.

3. **Logs w ./log/** — OASIS tworzy katalog `./log/` w CWD. W Docker container upewnij się że CWD jest writable.

4. **semaphore=128 default** — przy 100 agentach LLMAction bez ograniczenia możesz trafić w rate limit Anthropic API. Używaj `semaphore=10-20` dla bezpieczeństwa.

5. **Brak persystencji między sesjami** — każda symulacja startuje z czystej bazy. To jest zamierzone dla isolation. Wyniki eksportuj przez `get_simulation_summary()` zanim zamkniesz env.
