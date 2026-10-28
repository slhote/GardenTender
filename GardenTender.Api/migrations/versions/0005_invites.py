"""invites

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-26 18:07:37.129635
"""
from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('invites',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('garden_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(), nullable=False),
    sa.Column('via', sa.String(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('invited_by', sa.String(), nullable=True),
    sa.Column('approved_by', sa.String(), nullable=True),
    sa.Column('invitee_sub', sa.String(), nullable=True),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('accepted_by', sa.String(), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('declined_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['accepted_by'], ['users.sub'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['garden_id'], ['gardens.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['invited_by'], ['users.sub'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['approved_by'], ['users.sub'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['invitee_sub'], ['users.sub'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_invites_garden_id'), 'invites', ['garden_id'], unique=False)
    op.create_index(op.f('ix_invites_invitee_sub'), 'invites', ['invitee_sub'], unique=False)
    with op.batch_alter_table('garden_members') as batch:
        batch.add_column(sa.Column('approved_by', sa.String(), nullable=True))
        batch.create_foreign_key('fk_garden_members_approved_by', 'users', ['approved_by'], ['sub'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('garden_members') as batch:
        batch.drop_constraint('fk_garden_members_approved_by', type_='foreignkey')
        batch.drop_column('approved_by')
    op.drop_index(op.f('ix_invites_invitee_sub'), table_name='invites')
    op.drop_index(op.f('ix_invites_garden_id'), table_name='invites')
    op.drop_table('invites')
