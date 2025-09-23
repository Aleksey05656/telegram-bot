"""
@file: 20240917_002_add_sportmonks_tables.py
@description: Create Sportmonks ingestion tables and mapping helpers.
@dependencies: alembic, sqlalchemy
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20240917_002_add_sportmonks_tables"
down_revision = "20240917_001_create_predictions"
branch_labels = None
depends_on = None


async def upgrade() -> None:
    op.create_table(
        "sm_fixtures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), nullable=True),
        sa.Column("season_id", sa.Integer(), nullable=True),
        sa.Column("home_id", sa.Integer(), nullable=True),
        sa.Column("away_id", sa.Integer(), nullable=True),
        sa.Column("kickoff_utc", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("pulled_at_utc", sa.Text(), nullable=False),
    )
    op.create_index("idx_sm_fixtures_kickoff", "sm_fixtures", ["kickoff_utc"])
    op.create_index("idx_sm_fixtures_league", "sm_fixtures", ["league_id"])
    op.create_index("idx_sm_fixtures_season", "sm_fixtures", ["season_id"])

    op.create_table(
        "sm_teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name_norm", sa.Text(), nullable=False),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("pulled_at_utc", sa.Text(), nullable=False),
    )
    op.create_index("idx_sm_teams_name_norm", "sm_teams", ["name_norm"], unique=False)

    op.create_table(
        "sm_standings",
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("pulled_at_utc", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("league_id", "season_id", "team_id"),
    )
    op.create_index("idx_sm_standings_position", "sm_standings", ["position"])

    op.create_table(
        "sm_injuries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fixture_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("pulled_at_utc", sa.Text(), nullable=False),
    )
    op.create_index("idx_sm_injuries_team", "sm_injuries", ["team_id"])

    op.create_table(
        "sm_meta",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value_text", sa.Text(), nullable=False),
    )

    op.create_table(
        "map_teams",
        sa.Column("sm_team_id", sa.Integer(), primary_key=True),
        sa.Column("internal_team_id", sa.Integer(), nullable=False),
        sa.Column("name_norm", sa.Text(), nullable=False),
    )
    op.create_index("idx_map_teams_name_norm", "map_teams", ["name_norm"])

    op.create_table(
        "map_leagues",
        sa.Column("sm_league_id", sa.Integer(), primary_key=True),
        sa.Column("internal_code", sa.Text(), nullable=False),
    )


async def downgrade() -> None:
    op.drop_table("map_leagues")
    op.drop_index("idx_map_teams_name_norm", table_name="map_teams")
    op.drop_table("map_teams")
    op.drop_table("sm_meta")
    op.drop_index("idx_sm_injuries_team", table_name="sm_injuries")
    op.drop_table("sm_injuries")
    op.drop_index("idx_sm_standings_position", table_name="sm_standings")
    op.drop_table("sm_standings")
    op.drop_index("idx_sm_teams_name_norm", table_name="sm_teams")
    op.drop_table("sm_teams")
    op.drop_index("idx_sm_fixtures_season", table_name="sm_fixtures")
    op.drop_index("idx_sm_fixtures_league", table_name="sm_fixtures")
    op.drop_index("idx_sm_fixtures_kickoff", table_name="sm_fixtures")
    op.drop_table("sm_fixtures")
