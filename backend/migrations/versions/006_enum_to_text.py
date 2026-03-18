"""006 — Convert ENUM columns to TEXT — Issue #119.

Replaces PostgreSQL ENUM types with TEXT + CHECK constraints for flexibility.
ENUMs are problematic: adding values requires ALTER TYPE which can't run in transactions.

Revision ID: 006_enum_to_text
Revises: 005_timescaledb_retention
Create Date: 2026-03-18
"""

from alembic import op

revision = "006_enum_to_text"
down_revision = "005_timescaledb_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert ENUM columns to TEXT with CHECK constraints."""

    # ── alert_events.type ──
    # First check if column is ENUM and convert
    op.execute("""
        DO $$
        BEGIN
            -- Convert alert_events.type from ENUM to TEXT
            ALTER TABLE alert_events ALTER COLUMN type TYPE TEXT;
        EXCEPTION
            WHEN others THEN
                RAISE NOTICE 'alert_events.type already TEXT or error: %', SQLERRM;
        END $$;
    """)

    # Add CHECK constraint for valid alert types
    op.execute("""
        DO $$
        BEGIN
            ALTER TABLE alert_events
                ADD CONSTRAINT chk_alert_event_type
                CHECK (type IN (
                    'geopolitical', 'weather', 'supply_disruption', 'demand_shift',
                    'price_spike', 'port_congestion', 'sanctions', 'infrastructure',
                    'environmental', 'labor', 'policy', 'other'
                ));
        EXCEPTION
            WHEN duplicate_object THEN
                RAISE NOTICE 'Constraint chk_alert_event_type already exists';
        END $$;
    """)

    # ── commodity_prices.commodity ──
    op.execute("""
        DO $$
        BEGIN
            ALTER TABLE commodity_prices ALTER COLUMN commodity TYPE TEXT;
        EXCEPTION
            WHEN others THEN
                RAISE NOTICE 'commodity_prices.commodity already TEXT or error: %', SQLERRM;
        END $$;
    """)

    # Add CHECK constraint for valid commodities
    op.execute("""
        DO $$
        BEGIN
            ALTER TABLE commodity_prices
                ADD CONSTRAINT chk_commodity_prices_commodity
                CHECK (commodity IN (
                    'crude_oil', 'lng', 'diesel', 'jet_fuel', 'gasoline',
                    'coal', 'iron_ore', 'copper', 'wheat', 'corn',
                    'soybeans', 'rice', 'palm_oil', 'sugar', 'coffee',
                    'natural_gas', 'lpg', 'naphtha', 'fuel_oil'
                ));
        EXCEPTION
            WHEN duplicate_object THEN
                RAISE NOTICE 'Constraint chk_commodity_prices_commodity already exists';
        END $$;
    """)

    # Drop old ENUM types if they exist
    op.execute("DROP TYPE IF EXISTS alert_event_type CASCADE")
    op.execute("DROP TYPE IF EXISTS commodity_type CASCADE")


def downgrade() -> None:
    """Remove CHECK constraints (does not re-create ENUMs)."""
    op.execute("ALTER TABLE alert_events DROP CONSTRAINT IF EXISTS chk_alert_event_type")
    op.execute("ALTER TABLE commodity_prices DROP CONSTRAINT IF EXISTS chk_commodity_prices_commodity")
