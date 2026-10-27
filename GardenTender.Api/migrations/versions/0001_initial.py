"""initial: plants, users

Revision ID: 0001
Revises:
Create Date: 2026-10-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("species", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=False),
        sa.Column("water_every_days", sa.Integer(), nullable=False),
    )
    op.create_index("ix_plants_user_id", "plants", ["user_id"])
    op.create_table(
        "users",
        sa.Column("sub", sa.String(), primary_key=True),
        sa.Column("handle", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_handle", "users", ["handle"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_handle", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_plants_user_id", table_name="plants")
    op.drop_table("plants")
