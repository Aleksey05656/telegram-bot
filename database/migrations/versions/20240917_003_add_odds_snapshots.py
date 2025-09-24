"""
@file: 20240917_003_add_odds_snapshots.py
@description: Add odds_snapshots table storing latest odds per provider/market.
@dependencies: alembic, sqlalchemy
@created: 2025-09-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20240917_003_add_odds_snapshots"
down_revision = "20240917_002_add_sportmonks_tables"
branch_labels = None
depends_on = None


async def upgrade() -> None:
    op.create_table(
        "odds_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("pulled_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("match_key", sa.Text(), nullable=False),
        sa.Column("league", sa.Text(), nullable=True),
        sa.Column("kickoff_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("selection", sa.Text(), nullable=False),
        sa.Column("price_decimal", sa.Numeric(10, 4), nullable=False),
        sa.Column("extra_json", sa.Text(), nullable=True),
        sa.UniqueConstraint("provider", "match_key", "market", "selection", name="uq_odds_latest"),
    )
    op.create_index(
        "idx_odds_snapshots_match",
        "odds_snapshots",
        ["match_key", "market", "selection"],
    )


async def downgrade() -> None:
    op.drop_index("idx_odds_snapshots_match", table_name="odds_snapshots")
    op.drop_table("odds_snapshots")
