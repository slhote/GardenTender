"""garden requests

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-26 18:03:19.776001
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('garden_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('garden_id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('note', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('requested_by', sa.String(), nullable=False),
    sa.Column('decided_by', sa.String(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decision_reason', sa.String(), nullable=True),
    sa.Column('result', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['decided_by'], ['users.sub'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['garden_id'], ['gardens.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['requested_by'], ['users.sub'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_garden_requests_garden_id'), 'garden_requests', ['garden_id'], unique=False)
    op.create_index(op.f('ix_garden_requests_status'), 'garden_requests', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_garden_requests_status'), table_name='garden_requests')
    op.drop_index(op.f('ix_garden_requests_garden_id'), table_name='garden_requests')
    op.drop_table('garden_requests')
