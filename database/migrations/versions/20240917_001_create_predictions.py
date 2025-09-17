"""
@file: 20240917_001_create_predictions.py
@description: Initial async Alembic revision creating predictions storage.
@dependencies: alembic, sqlalchemy
@created: 2025-09-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20240917_001_create_predictions"
down_revision = None
branch_labels = None
depends_on = None


async def upgrade() -> None:
    op.create_table(
        "predictions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("fixture_id", sa.BigInteger(), nullable=False),
        sa.Column("league_id", sa.BigInteger(), nullable=True),
        sa.Column("season_id", sa.BigInteger(), nullable=True),
        sa.Column("home_team_id", sa.BigInteger(), nullable=True),
        sa.Column("away_team_id", sa.BigInteger(), nullable=True),
        sa.Column("match_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("model_name", sa.Text(), nullable=False, server_default=sa.text("'poisson'")),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("cache_version", sa.Text(), nullable=True),
        sa.Column("calibration_method", sa.Text(), nullable=True),
        sa.Column("model_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("lambda_home", sa.Numeric(8, 4), nullable=False),
        sa.Column("lambda_away", sa.Numeric(8, 4), nullable=False),
        sa.Column(
            "expected_total",
            sa.Numeric(8, 4),
            sa.Computed("lambda_home + lambda_away", persisted=True),
            nullable=False,
        ),
        sa.Column("prob_home_win", sa.Numeric(6, 5), nullable=False),
        sa.Column("prob_draw", sa.Numeric(6, 5), nullable=False),
        sa.Column("prob_away_win", sa.Numeric(6, 5), nullable=False),
        sa.Column("totals_probs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("btts_probs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("totals_corr_probs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("btts_corr_probs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=False),
        sa.Column("missing_ratio", sa.Numeric(6, 5), nullable=True),
        sa.Column("data_freshness_min", sa.Numeric(10, 2), nullable=True),
        sa.Column("penalties", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recommendations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("features_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("final_home_goals", sa.SmallInteger(), nullable=True),
        sa.Column("final_away_goals", sa.SmallInteger(), nullable=True),
        sa.Column("outcome_1x2", sa.Text(), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "prob_home_win >= 0 AND prob_home_win <= 1", name="chk_prob_home_win_range"
        ),
        sa.CheckConstraint("prob_draw >= 0 AND prob_draw <= 1", name="chk_prob_draw_range"),
        sa.CheckConstraint(
            "prob_away_win >= 0 AND prob_away_win <= 1", name="chk_prob_away_win_range"
        ),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="chk_confidence_range"),
        sa.CheckConstraint(
            "missing_ratio IS NULL OR (missing_ratio >= 0 AND missing_ratio <= 1)",
            name="chk_missing_ratio_range",
        ),
        sa.CheckConstraint(
            "abs((prob_home_win + prob_draw + prob_away_win) - 1.0) <= 0.01",
            name="chk_prob_1x2_sum_soft",
        ),
        sa.CheckConstraint(
            "outcome_1x2 IN ('home','draw','away') OR outcome_1x2 IS NULL",
            name="chk_outcome_1x2",
        ),
        sa.CheckConstraint("lambda_home >= 0 AND lambda_away >= 0", name="chk_lambda_positive"),
        sa.UniqueConstraint(
            "fixture_id",
            "model_version",
            name="uniq_predictions_fixture_model",
        ),
    )

    op.create_index("idx_predictions_fixture_id", "predictions", ["fixture_id"])
    op.create_index("idx_predictions_match_start", "predictions", ["match_start"])
    op.create_index("idx_predictions_model_version", "predictions", ["model_version"])
    op.create_index("idx_predictions_cache_version", "predictions", ["cache_version"])
    op.create_index(
        "idx_predictions_confidence",
        "predictions",
        ["confidence"],
        postgresql_using=None,
    )
    op.create_index(
        "idx_predictions_reco_gin",
        "predictions",
        ["recommendations"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "idx_predictions_match_start_settled",
        "predictions",
        ["match_start"],
        postgresql_where=sa.text("settled_at IS NULL"),
    )
    op.create_index(
        "idx_predictions_settled",
        "predictions",
        ["settled_at"],
        postgresql_where=sa.text("settled_at IS NOT NULL"),
    )

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION trg_predictions_touch_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
              NEW.updated_at := NOW();
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    op.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS predictions_touch_updated_at ON predictions;
            CREATE TRIGGER predictions_touch_updated_at
            BEFORE UPDATE ON predictions
            FOR EACH ROW
            EXECUTE FUNCTION trg_predictions_touch_updated_at();
            """
        )
    )


async def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS predictions_touch_updated_at ON predictions;"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS trg_predictions_touch_updated_at();"))
    op.drop_index("idx_predictions_settled", table_name="predictions")
    op.drop_index("idx_predictions_match_start_settled", table_name="predictions")
    op.drop_index("idx_predictions_reco_gin", table_name="predictions")
    op.drop_index("idx_predictions_confidence", table_name="predictions")
    op.drop_index("idx_predictions_cache_version", table_name="predictions")
    op.drop_index("idx_predictions_model_version", table_name="predictions")
    op.drop_index("idx_predictions_match_start", table_name="predictions")
    op.drop_index("idx_predictions_fixture_id", table_name="predictions")
    op.drop_table("predictions")
