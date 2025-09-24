"""
"""
/**
 * @file: database/migrations/versions/20241005_004_value_v1_4.py
 * @description: Value v1.4 schema updates for odds history, closing lines and picks ledger.
 * @dependencies: alembic, sqlalchemy
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20241005_004_value_v1_4"
down_revision = "20240917_003_add_odds_snapshots"
branch_labels = None
depends_on = None


async def upgrade() -> None:
    with op.batch_alter_table("odds_snapshots") as batch:
        try:
            batch.drop_constraint("uq_odds_latest", type_="unique")
        except Exception:  # pragma: no cover - constraint may be unnamed in legacy dbs
            pass
        batch.create_unique_constraint(
            "uq_odds_latest",
            ["provider", "match_key", "market", "selection", "pulled_at_utc"],
        )
    op.create_index(
        "idx_odds_snapshots_match_time",
        "odds_snapshots",
        ["match_key", "market", "selection", "pulled_at_utc"],
    )
    op.create_table(
        "closing_lines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_key", sa.Text(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("selection", sa.Text(), nullable=False),
        sa.Column("consensus_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("consensus_probability", sa.Numeric(10, 6), nullable=False),
        sa.Column("provider_count", sa.Integer(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("pulled_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("match_key", "market", "selection", name="uq_closing_lines"),
    )
    op.create_table(
        "picks_ledger",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("match_key", sa.Text(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("selection", sa.Text(), nullable=False),
        sa.Column("stake", sa.Numeric(12, 2), nullable=False, server_default="1.0"),
        sa.Column("price_taken", sa.Numeric(12, 4), nullable=False),
        sa.Column("model_probability", sa.Numeric(10, 6), nullable=False),
        sa.Column("market_probability", sa.Numeric(10, 6), nullable=False),
        sa.Column("edge_pct", sa.Numeric(10, 4), nullable=False),
        sa.Column("confidence", sa.Numeric(10, 6), nullable=False),
        sa.Column("pulled_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kickoff_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consensus_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("consensus_method", sa.Text(), nullable=False),
        sa.Column("consensus_provider_count", sa.Integer(), nullable=False),
        sa.Column("clv_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("closing_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("closing_pulled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closing_method", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id",
            "match_key",
            "market",
            "selection",
            "pulled_at_utc",
            name="uq_picks_ledger_entry",
        ),
    )
    op.create_index(
        "picks_ledger_user_idx",
        "picks_ledger",
        ["user_id", "created_at"],
    )
    op.create_index(
        "picks_ledger_match_idx",
        "picks_ledger",
        ["match_key", "market", "selection"],
    )


async def downgrade() -> None:
    op.drop_index("picks_ledger_match_idx", table_name="picks_ledger")
    op.drop_index("picks_ledger_user_idx", table_name="picks_ledger")
    op.drop_table("picks_ledger")
    op.drop_table("closing_lines")
    op.drop_index("idx_odds_snapshots_match_time", table_name="odds_snapshots")
    with op.batch_alter_table("odds_snapshots") as batch:
        try:
            batch.drop_constraint("uq_odds_latest", type_="unique")
        except Exception:  # pragma: no cover - constraint may be unnamed
            pass
        batch.create_unique_constraint(
            "uq_odds_latest",
            ["provider", "match_key", "market", "selection"],
        )
