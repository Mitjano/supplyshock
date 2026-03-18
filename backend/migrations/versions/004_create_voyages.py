"""Create voyages table for automatic trip tracking.

Issue #41: Voyage detection — port enter/exit via geofencing

Revision ID: 004
Revises: 003
Create Date: 2026-03-17

"""
from typing import Sequence, Union

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic import op

    op.execute("""
        CREATE TYPE voyage_status AS ENUM (
            'underway', 'arrived', 'floating_storage', 'completed'
        );
    """)

    op.execute("""
        CREATE TABLE voyages (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            mmsi                BIGINT NOT NULL,
            imo                 BIGINT,
            vessel_name         TEXT,
            vessel_type         vessel_type NOT NULL DEFAULT 'other',
            origin_port_id      UUID REFERENCES ports(id),
            dest_port_id        UUID REFERENCES ports(id),
            departure_time      TIMESTAMPTZ,
            arrival_time        TIMESTAMPTZ,
            status              voyage_status NOT NULL DEFAULT 'underway',
            laden_status        TEXT,           -- 'laden', 'ballast', 'unknown'
            cargo_type          TEXT,           -- commodity name from origin port
            volume_estimate     DECIMAL(14,2), -- metric tonnes
            distance_nm         DECIMAL(10,2), -- nautical miles (accumulated)
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX idx_voyages_mmsi ON voyages(mmsi, departure_time DESC);
        CREATE INDEX idx_voyages_status ON voyages(status) WHERE status IN ('underway', 'arrived');
        CREATE INDEX idx_voyages_origin ON voyages(origin_port_id);
        CREATE INDEX idx_voyages_dest ON voyages(dest_port_id);
        CREATE INDEX idx_voyages_departure ON voyages(departure_time DESC);
        CREATE INDEX idx_voyages_cargo ON voyages(cargo_type) WHERE cargo_type IS NOT NULL;

        CREATE TRIGGER set_updated_at BEFORE UPDATE ON voyages
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
    """)


def downgrade() -> None:
    from alembic import op

    op.execute("DROP TABLE IF EXISTS voyages CASCADE;")
    op.execute("DROP TYPE IF EXISTS voyage_status;")
