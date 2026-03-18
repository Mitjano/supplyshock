"""005 — TimescaleDB retention policies — Issue #104.

Revision ID: 005_timescaledb_retention
Revises: 004_create_voyages
Create Date: 2026-03-18
"""

from alembic import op

revision = "005_timescaledb_retention"
down_revision = "004_create_voyages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add TimescaleDB retention policies for time-series tables."""

    # Ensure TimescaleDB extension is enabled
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # Convert tables to hypertables if not already (safe: IF NOT EXISTS is implicit
    # because create_hypertable raises notice if already a hypertable).
    # We wrap in DO blocks to handle the case where they're already hypertables.
    hypertables = [
        ("vessel_positions", "time"),
        ("commodity_prices", "time"),
        ("chokepoint_status", "time"),
        ("alert_events", "time"),
        ("eia_inventories", "time"),
    ]

    for table, col in hypertables:
        op.execute(f"""
            DO $$
            BEGIN
                PERFORM create_hypertable('{table}', '{col}',
                    migrate_data => true, if_not_exists => true);
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Hypertable {table} already exists or error: %', SQLERRM;
            END $$;
        """)

    # Retention policies — automatically drop old data
    # vessel_positions: keep 90 days (high-frequency AIS data)
    op.execute("""
        SELECT add_retention_policy('vessel_positions', INTERVAL '90 days', if_not_exists => true)
    """)

    # chokepoint_status: keep 1 year
    op.execute("""
        SELECT add_retention_policy('chokepoint_status', INTERVAL '365 days', if_not_exists => true)
    """)

    # alert_events: keep 2 years
    op.execute("""
        SELECT add_retention_policy('alert_events', INTERVAL '730 days', if_not_exists => true)
    """)

    # Compression policies for older data
    # vessel_positions: compress after 7 days
    op.execute("""
        DO $$
        BEGIN
            ALTER TABLE vessel_positions SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'mmsi'
            );
            PERFORM add_compression_policy('vessel_positions', INTERVAL '7 days', if_not_exists => true);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Compression setup for vessel_positions: %', SQLERRM;
        END $$;
    """)

    # chokepoint_status: compress after 30 days
    op.execute("""
        DO $$
        BEGIN
            ALTER TABLE chokepoint_status SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'node_id'
            );
            PERFORM add_compression_policy('chokepoint_status', INTERVAL '30 days', if_not_exists => true);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Compression setup for chokepoint_status: %', SQLERRM;
        END $$;
    """)


def downgrade() -> None:
    """Remove retention and compression policies."""
    for table in ["vessel_positions", "chokepoint_status", "alert_events"]:
        op.execute(f"""
            DO $$
            BEGIN
                PERFORM remove_retention_policy('{table}', if_exists => true);
            EXCEPTION WHEN OTHERS THEN NULL;
            END $$;
        """)
    for table in ["vessel_positions", "chokepoint_status"]:
        op.execute(f"""
            DO $$
            BEGIN
                PERFORM remove_compression_policy('{table}', if_exists => true);
            EXCEPTION WHEN OTHERS THEN NULL;
            END $$;
        """)
