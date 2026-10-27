"""qr codes

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-26 18:10:07.083364
"""
from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('qr_codes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('token', sa.String(), nullable=False),
    sa.Column('garden_id', sa.Integer(), nullable=False),
    sa.Column('target_type', sa.String(), nullable=False),
    sa.Column('plant_id', sa.Integer(), nullable=True),
    sa.Column('label', sa.String(), nullable=True),
    sa.Column('created_by', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.sub'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['garden_id'], ['gardens.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token')
    )
    op.create_index(op.f('ix_qr_codes_garden_id'), 'qr_codes', ['garden_id'], unique=False)
    op.create_index(op.f('ix_qr_codes_plant_id'), 'qr_codes', ['plant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_qr_codes_plant_id'), table_name='qr_codes')
    op.drop_index(op.f('ix_qr_codes_garden_id'), table_name='qr_codes')
    op.drop_table('qr_codes')
