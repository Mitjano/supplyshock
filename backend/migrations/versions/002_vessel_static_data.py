"""Add vessel_static_data table and radius_km to ports.

Issue #39: AIS Type 5 static data ingestion
Issue #40 prep: port geofencing radius

Revision ID: 002
Revises: 001
Create Date: 2026-03-17

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic import op
    import sqlalchemy as sa

    # -- vessel_static_data: stores AIS Type 5 messages (one row per MMSI) --
    op.execute("""
        CREATE TABLE vessel_static_data (
            mmsi            BIGINT PRIMARY KEY,
            imo             BIGINT,
            vessel_name     TEXT,
            callsign        TEXT,
            ship_type       INT,                    -- raw AIS ship type code
            vessel_type     vessel_type NOT NULL DEFAULT 'other',
            dim_a           INT,                    -- bow to AIS antenna (m)
            dim_b           INT,                    -- AIS antenna to stern (m)
            dim_c           INT,                    -- port side to antenna (m)
            dim_d           INT,                    -- antenna to starboard (m)
            length_m        DECIMAL(7,2),           -- computed: dim_a + dim_b
            beam_m          DECIMAL(7,2),           -- computed: dim_c + dim_d
            dwt_estimate    DECIMAL(12,2),          -- estimated DWT from dimensions
            max_draught     DECIMAL(5,2),           -- metres
            flag_country    TEXT,
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX idx_vsd_imo ON vessel_static_data(imo) WHERE imo IS NOT NULL;
        CREATE INDEX idx_vsd_type ON vessel_static_data(vessel_type);
        CREATE INDEX idx_vsd_updated ON vessel_static_data(updated_at DESC);

        -- Auto-update updated_at trigger
        CREATE TRIGGER set_updated_at BEFORE UPDATE ON vessel_static_data
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
    """)

    # -- Add radius_km to ports for geofencing (Issue #40 prep) --
    op.execute("""
        ALTER TABLE ports ADD COLUMN IF NOT EXISTS radius_km DECIMAL(6,2) DEFAULT 5.0;
    """)


def downgrade() -> None:
    from alembic import op

    op.execute("DROP TABLE IF EXISTS vessel_static_data CASCADE;")
    op.execute("ALTER TABLE ports DROP COLUMN IF EXISTS radius_km;")
