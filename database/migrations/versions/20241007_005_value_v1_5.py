"""
/**
 * @file: database/migrations/versions/20241007_005_value_v1_5.py
 * @description: Value v1.5 schema updates for best-price routing, provider stats and ROI.
 * @dependencies: alembic, sqlalchemy
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20241007_005_value_v1_5"
down_revision = "20241005_004_value_v1_4"
branch_labels = None
depends_on = None


async def upgrade() -> None:
    with op.batch_alter_table("picks_ledger") as batch:
        batch.add_column(
            sa.Column(
                "provider_price_decimal",
                sa.Numeric(12, 4),
                nullable=False,
                server_default="0.0",
            )
        )
        batch.add_column(
            sa.Column(
                "consensus_price_decimal",
                sa.Numeric(12, 4),
                nullable=False,
                server_default="0.0",
            )
        )
        batch.add_column(sa.Column("outcome", sa.Text(), nullable=True))
        batch.add_column(sa.Column("roi", sa.Numeric(10, 4), nullable=True))

    op.execute(
        """
        UPDATE picks_ledger
           SET provider_price_decimal = price_taken
         WHERE provider_price_decimal = 0 OR provider_price_decimal IS NULL
        """
    )
    op.execute(
        """
        UPDATE picks_ledger
           SET consensus_price_decimal = consensus_price
         WHERE consensus_price_decimal = 0 OR consensus_price_decimal IS NULL
        """
    )

    op.create_table(
        "provider_stats",
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("league", sa.Text(), nullable=False),
        sa.Column("coverage", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("fresh_share", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("lag_ms", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("stability", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("bias", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("score", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("provider", "market", "league"),
    )

    try:
        op.create_index(
            "idx_odds_snapshots_match_time",
            "odds_snapshots",
            ["match_key", "market", "selection", "pulled_at_utc"],
        )
    except Exception:  # pragma: no cover - index may already exist on legacy dbs
        pass


async def downgrade() -> None:
    op.drop_table("provider_stats")

    with op.batch_alter_table("picks_ledger") as batch:
        batch.drop_column("roi")
        batch.drop_column("outcome")
        batch.drop_column("consensus_price_decimal")
        batch.drop_column("provider_price_decimal")
