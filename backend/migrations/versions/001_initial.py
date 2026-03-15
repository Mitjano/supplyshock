"""initial - schema loaded via docker-entrypoint-initdb.d

Revision ID: 001
Revises: None
Create Date: 2026-03-15

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Schema is loaded from schema.sql via docker-entrypoint-initdb.d
    # This migration exists as a baseline marker for Alembic
    pass


def downgrade() -> None:
    pass
