"""Seed the historical_events table with 10 landmark supply-chain events.

Usage:
    cd backend && python -m scripts.seed_historical_events
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings

EVENTS = [
    {
        "slug": "ever-given-2021",
        "title": "Ever Given Suez Canal Blockage",
        "description": "The container ship Ever Given ran aground in the Suez Canal on 23 March 2021, blocking one of the world's busiest trade routes for six days.",
        "event_date": "2021-03-23",
        "end_date": "2021-03-29",
        "region": "Middle East",
        "commodities": "oil,lng,containers",
        "impact_summary": "Oil prices spiked ~6% during the blockage. An estimated $9.6B of goods were delayed daily.",
    },
    {
        "slug": "russia-ukraine-2022",
        "title": "Russia-Ukraine War",
        "description": "Russia's invasion of Ukraine in February 2022 disrupted global energy and grain markets.",
        "event_date": "2022-02-24",
        "end_date": None,
        "region": "Europe",
        "commodities": "oil,natural_gas,wheat,corn,fertilizer",
        "impact_summary": "European natural gas prices surged 400%+. Wheat futures hit all-time highs. Global fertilizer costs doubled.",
    },
    {
        "slug": "houthi-red-sea-2023",
        "title": "Houthi Red Sea Attacks",
        "description": "Houthi rebels began attacking commercial vessels in the Red Sea in late 2023, forcing major rerouting via the Cape of Good Hope.",
        "event_date": "2023-11-19",
        "end_date": None,
        "region": "Middle East",
        "commodities": "oil,lng,containers",
        "impact_summary": "Container shipping rates tripled. Transit times increased 10-14 days. ~15% of global trade affected.",
    },
    {
        "slug": "covid-supply-chain-2020",
        "title": "COVID-19 Supply Chain Crisis",
        "description": "The global pandemic caused unprecedented supply chain disruptions starting early 2020.",
        "event_date": "2020-03-11",
        "end_date": "2022-06-30",
        "region": "Global",
        "commodities": "containers,semiconductors,oil",
        "impact_summary": "Container rates rose 10x. Port congestion worldwide. Semiconductor shortage lasted 2+ years.",
    },
    {
        "slug": "opec-plus-cuts-2023",
        "title": "OPEC+ Production Cuts",
        "description": "OPEC+ announced surprise voluntary production cuts of 1.66 million barrels/day in April 2023.",
        "event_date": "2023-04-02",
        "end_date": None,
        "region": "Global",
        "commodities": "oil",
        "impact_summary": "Brent crude jumped ~8% in the week following the announcement.",
    },
    {
        "slug": "nord-stream-2022",
        "title": "Nord Stream Pipeline Sabotage",
        "description": "Explosions damaged the Nord Stream 1 and 2 pipelines under the Baltic Sea in September 2022.",
        "event_date": "2022-09-26",
        "end_date": "2022-09-26",
        "region": "Europe",
        "commodities": "natural_gas",
        "impact_summary": "European gas prices spiked 12% intraday. Accelerated Europe's pivot away from Russian gas.",
    },
    {
        "slug": "australia-floods-2022",
        "title": "Australia East Coast Floods",
        "description": "Severe flooding in Queensland and New South Wales disrupted coal mining and logistics in early 2022.",
        "event_date": "2022-02-23",
        "end_date": "2022-04-15",
        "region": "Asia-Pacific",
        "commodities": "coal,iron_ore",
        "impact_summary": "Thermal coal prices rose 25%. Multiple coal mines suspended operations. Rail networks severed.",
    },
    {
        "slug": "china-coal-ban-2020",
        "title": "China Australian Coal Import Ban",
        "description": "China imposed an unofficial ban on Australian coal imports in late 2020 amid diplomatic tensions.",
        "event_date": "2020-10-12",
        "end_date": "2023-01-15",
        "region": "Asia-Pacific",
        "commodities": "coal",
        "impact_summary": "Redirected global coal trade flows. Australian coal diverted to India/Japan. Chinese domestic prices surged.",
    },
    {
        "slug": "texas-freeze-2021",
        "title": "Texas Winter Storm Uri",
        "description": "An unprecedented winter storm caused widespread power and refinery outages across Texas in February 2021.",
        "event_date": "2021-02-13",
        "end_date": "2021-02-20",
        "region": "North America",
        "commodities": "oil,natural_gas,petrochemicals",
        "impact_summary": "Natural gas spot prices briefly hit $200/MMBtu. ~4M barrels/day of refining capacity offline. Petrochemical shortages lasted months.",
    },
    {
        "slug": "panama-drought-2023",
        "title": "Panama Canal Drought Restrictions",
        "description": "Record drought in 2023 forced the Panama Canal Authority to drastically reduce daily vessel transits.",
        "event_date": "2023-07-30",
        "end_date": "2024-02-15",
        "region": "Americas",
        "commodities": "lng,containers,grain",
        "impact_summary": "Daily transits cut from ~38 to 22. Wait times exceeded 21 days. LNG and grain shipments rerouted.",
    },
]


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        for ev in EVENTS:
            # Upsert by slug
            await db.execute(
                text("""
                    INSERT INTO historical_events
                        (slug, title, description, event_date, end_date, region, commodities, impact_summary)
                    VALUES
                        (:slug, :title, :description, :event_date, :end_date, :region, :commodities, :impact_summary)
                    ON CONFLICT (slug) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        event_date = EXCLUDED.event_date,
                        end_date = EXCLUDED.end_date,
                        region = EXCLUDED.region,
                        commodities = EXCLUDED.commodities,
                        impact_summary = EXCLUDED.impact_summary
                """),
                ev,
            )
        await db.commit()
        print(f"Seeded {len(EVENTS)} historical events.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
