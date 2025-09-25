"""
@file: 20241012_006_provider_reliability_v2.py
@description: Introduce Bayesian provider reliability schema with aggregated stats and composite odds index.
@dependencies: alembic, sqlalchemy
@created: 2025-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20241012_006_provider_reliability_v2"
down_revision = "20241007_005_value_v1_5"
branch_labels = None
depends_on = None


def _drop_existing_provider_stats() -> None:
    try:
        op.drop_table("provider_stats")
    except sa.exc.NoSuchTableError:  # pragma: no cover - defensive branch
        return


async def upgrade() -> None:
    _drop_existing_provider_stats()
    op.create_table(
        "provider_stats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("league", sa.Text(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("samples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fresh_success", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fresh_fail", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_sum_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_sq_sum", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stability_z_sum", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stability_z_abs_sum", sa.Float(), nullable=False, server_default="0"),
        sa.Column("closing_within_tol", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("closing_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at_utc", sa.Text(), nullable=False),
        sa.UniqueConstraint("provider", "league", "market", name="uq_provider_scope"),
    )
    op.create_index(
        "idx_odds_snapshots_match_market_time",
        "odds_snapshots",
        ["match_key", "market", "selection", "pulled_at_utc"],
        unique=False,
    )


async def downgrade() -> None:
    op.drop_index("idx_odds_snapshots_match_market_time", table_name="odds_snapshots")
    op.drop_table("provider_stats")
    op.create_table(
        "provider_stats",
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("league", sa.Text(), nullable=False),
        sa.Column("coverage", sa.Float(), nullable=False),
        sa.Column("fresh_share", sa.Float(), nullable=False),
        sa.Column("lag_ms", sa.Float(), nullable=False),
        sa.Column("stability", sa.Float(), nullable=False),
        sa.Column("bias", sa.Float(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("provider", "market", "league"),
    )
