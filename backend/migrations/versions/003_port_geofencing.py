"""Add PostGIS spatial index and is_in_port() function.

Issue #40: Port geofencing — radius-based enter/exit detection

Revision ID: 003
Revises: 002
Create Date: 2026-03-17

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic import op

    # PostGIS extension (idempotent — may already exist from schema.sql)
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # Add unlocode column to ports (UN/LOCODE e.g. 'AUMEL' for Melbourne)
    op.execute("""
        ALTER TABLE ports ADD COLUMN IF NOT EXISTS unlocode TEXT;
        CREATE INDEX IF NOT EXISTS idx_ports_unlocode ON ports(unlocode) WHERE unlocode IS NOT NULL;
    """)

    # PostGIS geography index — enables ST_DWithin with accurate km distances
    # Replaces the basic point() GIST index for distance-based queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ports_geog
            ON ports USING GIST (
                ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
            );
    """)

    # SQL function: is_in_port(lat, lon) → returns port row or NULL
    # Uses ST_DWithin on geography for accurate spherical distance in metres
    op.execute("""
        CREATE OR REPLACE FUNCTION is_in_port(
            p_lat DOUBLE PRECISION,
            p_lon DOUBLE PRECISION
        )
        RETURNS TABLE (
            port_id     UUID,
            port_name   TEXT,
            distance_km DOUBLE PRECISION
        )
        LANGUAGE sql STABLE
        AS $$
            SELECT
                p.id AS port_id,
                p.name AS port_name,
                ST_Distance(
                    ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography
                ) / 1000.0 AS distance_km
            FROM ports p
            WHERE ST_DWithin(
                ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography,
                ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography,
                p.radius_km * 1000  -- ST_DWithin uses metres for geography
            )
            ORDER BY distance_km ASC
            LIMIT 1;
        $$;
    """)

    # SQL function: vessels_in_port(port_id) → returns vessels currently in port radius
    op.execute("""
        CREATE OR REPLACE FUNCTION vessels_in_port(p_port_id UUID)
        RETURNS TABLE (
            mmsi        BIGINT,
            vessel_name TEXT,
            vessel_type vessel_type,
            distance_km DOUBLE PRECISION,
            speed_knots DECIMAL(5,2),
            last_seen   TIMESTAMPTZ
        )
        LANGUAGE sql STABLE
        AS $$
            SELECT
                v.mmsi,
                v.vessel_name,
                v.vessel_type,
                ST_Distance(
                    ST_SetSRID(ST_MakePoint(v.longitude, v.latitude), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography
                ) / 1000.0 AS distance_km,
                v.speed_knots,
                v.time AS last_seen
            FROM latest_vessel_positions v, ports p
            WHERE p.id = p_port_id
              AND ST_DWithin(
                  ST_SetSRID(ST_MakePoint(v.longitude, v.latitude), 4326)::geography,
                  ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography,
                  p.radius_km * 1000
              )
            ORDER BY distance_km ASC;
        $$;
    """)


def downgrade() -> None:
    from alembic import op

    op.execute("DROP FUNCTION IF EXISTS vessels_in_port(UUID);")
    op.execute("DROP FUNCTION IF EXISTS is_in_port(DOUBLE PRECISION, DOUBLE PRECISION);")
    op.execute("DROP INDEX IF EXISTS idx_ports_geog;")
    op.execute("DROP INDEX IF EXISTS idx_ports_unlocode;")
    op.execute("ALTER TABLE ports DROP COLUMN IF EXISTS unlocode;")
