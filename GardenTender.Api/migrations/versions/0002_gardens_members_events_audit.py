"""gardens members events audit

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-26 17:23:57.102678
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('admin_audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('actor_sub', sa.String(), nullable=False),
    sa.Column('method', sa.String(), nullable=False),
    sa.Column('path', sa.String(), nullable=False),
    sa.Column('path_params', sa.JSON(), nullable=False),
    sa.Column('body', sa.JSON(), nullable=True),
    sa.Column('status_code', sa.Integer(), nullable=False),
    sa.Column('garden_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_audit_log_actor_sub'), 'admin_audit_log', ['actor_sub'], unique=False)
    op.create_index(op.f('ix_admin_audit_log_created_at'), 'admin_audit_log', ['created_at'], unique=False)
    op.create_index(op.f('ix_admin_audit_log_garden_id'), 'admin_audit_log', ['garden_id'], unique=False)
    op.create_table('gardens',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('created_by', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.sub'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gardens_deleted_at'), 'gardens', ['deleted_at'], unique=False)
    op.create_table('garden_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('garden_id', sa.Integer(), nullable=False),
    sa.Column('actor_sub', sa.String(), nullable=False),
    sa.Column('via_global_admin', sa.Boolean(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['garden_id'], ['gardens.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_garden_events_garden_id'), 'garden_events', ['garden_id'], unique=False)
    op.create_table('garden_members',
    sa.Column('garden_id', sa.Integer(), nullable=False),
    sa.Column('user_sub', sa.String(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('invited_by', sa.String(), nullable=True),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['garden_id'], ['gardens.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['invited_by'], ['users.sub'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_sub'], ['users.sub'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('garden_id', 'user_sub')
    )
    op.create_index(op.f('ix_garden_members_user_sub'), 'garden_members', ['user_sub'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_garden_members_user_sub'), table_name='garden_members')
    op.drop_table('garden_members')
    op.drop_index(op.f('ix_garden_events_garden_id'), table_name='garden_events')
    op.drop_table('garden_events')
    op.drop_index(op.f('ix_gardens_deleted_at'), table_name='gardens')
    op.drop_table('gardens')
    op.drop_index(op.f('ix_admin_audit_log_garden_id'), table_name='admin_audit_log')
    op.drop_index(op.f('ix_admin_audit_log_created_at'), table_name='admin_audit_log')
    op.drop_index(op.f('ix_admin_audit_log_actor_sub'), table_name='admin_audit_log')
    op.drop_table('admin_audit_log')
