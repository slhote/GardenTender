"""plants belong to gardens (existing plants are dropped: no real data yet)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _plant_columns() -> list:
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("species", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=False),
        sa.Column("water_every_days", sa.Integer(), nullable=False),
    ]


def upgrade() -> None:
    op.drop_index("ix_plants_user_id", table_name="plants")
    op.drop_table("plants")
    op.create_table(
        "plants",
        *_plant_columns(),
        sa.Column("garden_id", sa.Integer(), sa.ForeignKey("gardens.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.String(), sa.ForeignKey("users.sub", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_plants_garden_id", "plants", ["garden_id"])


def downgrade() -> None:
    op.drop_index("ix_plants_garden_id", table_name="plants")
    op.drop_table("plants")
    op.create_table("plants", *_plant_columns(), sa.Column("user_id", sa.String(), nullable=False))
    op.create_index("ix_plants_user_id", "plants", ["user_id"])
