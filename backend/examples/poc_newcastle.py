"""
OASIS Commodity Fork — Newcastle Flood POC

Tests that the commodity fork produces sensible economic behavior
for a coal supply disruption scenario.

Run: cd backend && python simulation/poc_newcastle.py
Expected: < 3 min, < $0.50 LLM cost, >=60% agents react with buy action.

Requirements:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-...
"""

import asyncio
import os
import sqlite3
import sys
import time

# Ensure oasis_fork is importable from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.oasis_fork import ActionType, AgentGraph, LLMAction, ManualAction, OasisEnv
from simulation.oasis_fork.social_platform.typing import DefaultPlatformType
from simulation.oasis_fork.social_platform.config.user import CommodityAgentInfo
from simulation.oasis_fork.social_agent.agent import SocialAgent
from simulation.oasis_fork.commodity.agents import make_coal_trader, make_government_agent
from simulation.oasis_fork.commodity.market import compute_consensus_price, get_simulation_summary
from simulation.oasis_fork.model import ClaudeModel

DB_PATH = "/tmp/poc_newcastle.db"


async def main():
    start_time = time.time()

    # Clean previous run
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # Model: Claude Haiku — cheapest capable model
    haiku = ClaudeModel(
        model_id="claude-haiku-4-5-20251001",
        max_tokens=256,
        temperature=0.7,
    )

    graph = AgentGraph()

    # 10 LLM traders (different regions)
    regions = ["JP", "JP", "JP", "CN", "CN", "KR", "KR", "DE", "JP", "CN"]
    for i, region in enumerate(regions):
        make_coal_trader(i, graph, haiku, region=region)

    # 1 government agent (Australia — source country)
    make_government_agent(10, graph, haiku, country="AU")

    # 89 rule-based shippers (ManualAction DO_NOTHING — zero LLM cost)
    for i in range(11, 100):
        agent = SocialAgent(
            agent_id=i,
            user_info=CommodityAgentInfo(
                user_name=f"shipper_{i}",
                agent_type="shipper",
                commodity="coal",
                description="Bulk carrier operator, Newcastle to Japan route.",
            ),
            agent_graph=graph,
            model=None,
            available_actions=[ActionType.DO_NOTHING],
        )
        graph.add_agent(agent)

    print(f"Created {len(graph)} agents (11 LLM + 89 rule-based)")

    # Initialize environment with COMMODITY platform
    env = OasisEnv(
        agent_graph=graph,
        platform=DefaultPlatformType.COMMODITY,
        database_path=DB_PATH,
        semaphore=10,
    )

    await env.reset()
    print("Environment initialized.")

    # Collect agent references
    all_agents = list(graph.get_agents())
    llm_agents = [(aid, a) for aid, a in all_agents if aid <= 10]
    rule_agents = [(aid, a) for aid, a in all_agents if aid > 10]

    # STEP 0: Inject disruption seed event
    seed_agent = all_agents[0][1]
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
        seed_agent: ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": seed_content},
        )
    })
    print("Seed event injected.")

    # STEPS 1-5: LLM agents react, rule-based agents do nothing
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
                action_args={},
            )
        await env.step(actions)

    await env.close()

    elapsed = time.time() - start_time

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

    # Price views
    cursor.execute(
        "SELECT COUNT(*), ROUND(AVG(price_view), 2), ROUND(MIN(price_view), 2), ROUND(MAX(price_view), 2) "
        "FROM trade WHERE price_view > 0"
    )
    price_row = cursor.fetchone()
    if price_row and price_row[0]:
        print(f"\nTrade price views: avg=${price_row[1]}, min=${price_row[2]}, max=${price_row[3]} ({price_row[0]} records)")

    # Consensus price from market_state
    consensus = compute_consensus_price("coal", DB_PATH)
    print(f"\nConsensus price: ${consensus:.2f}/t" if consensus else "\nNo consensus price recorded.")
    print(f"Baseline price: $118.40/t")
    if consensus:
        pct_change = (consensus - 118.40) / 118.40 * 100
        print(f"Price change: {pct_change:+.1f}%")

    # Vessel reroutes
    cursor.execute("SELECT COUNT(*) FROM vessel_decision")
    reroutes = cursor.fetchone()[0]
    print(f"\nVessel reroutes: {reroutes}")

    # Government measures
    cursor.execute("SELECT COUNT(*) FROM trace WHERE action = 'impose_measure'")
    measures = cursor.fetchone()[0]
    print(f"Government measures: {measures}")

    # Trace summary
    cursor.execute("SELECT action, COUNT(*) FROM trace GROUP BY action ORDER BY COUNT(*) DESC")
    trace_rows = cursor.fetchall()
    print(f"\nAction trace:")
    for action, count in trace_rows:
        print(f"  {action}: {count}")

    conn.close()

    # Summary
    summary = get_simulation_summary(DB_PATH)
    print(f"\nSimulation summary: {len(summary['trade_counts'])} trade types, "
          f"{len(summary['reroutes'])} reroute patterns, "
          f"{len(summary['measures'])} measures")

    # ── ACCEPTANCE CRITERIA ──────────────────────────────────────
    print(f"\n{'='*60}")
    print("ACCEPTANCE CRITERIA")
    print(f"{'='*60}")

    checks = [
        (
            ">=60% LLM agents react with buy",
            buy_trades >= 6,
            f"{buy_trades}/10 agents bought",
        ),
        (
            "Consensus price > baseline ($118.40)",
            consensus is not None and consensus > 118.40,
            f"${consensus:.2f}" if consensus else "no data",
        ),
        (
            "Total trades > 0",
            total_trades > 0,
            f"{total_trades} trades",
        ),
        (
            "Heterogeneous reactions (>=2 action types)",
            len(trades) >= 2,
            f"{len(trades)} distinct actions",
        ),
        (
            "Execution time < 3 minutes",
            elapsed < 180,
            f"{elapsed:.1f}s",
        ),
    ]

    passed = 0
    for label, result, detail in checks:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {label} ({detail})")
        if result:
            passed += 1

    print(f"\n{passed}/{len(checks)} criteria passed in {elapsed:.1f}s")

    if passed < len(checks):
        print("\nDebug hints:")
        print("  - Check agent descriptions in make_coal_trader()")
        print("  - Check seed event content is visible in agent feed")
        print("  - Increase max_rec_post_len if agents don't see events")
        print("  - Check ANTHROPIC_API_KEY is set")


if __name__ == "__main__":
    asyncio.run(main())
