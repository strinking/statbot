"""Add threads and thread_members

Revision ID: 4ad50631992f
Revises: 74bc9658d7ff
Create Date: 2022-10-01 22:31:49.574159

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4ad50631992f'
down_revision = '74bc9658d7ff'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('threads',
    sa.Column('thread_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('invitable', sa.Boolean(), nullable=True),
    sa.Column('locked', sa.Boolean(), nullable=True),
    sa.Column('archived', sa.Boolean(), nullable=True),
    sa.Column('auto_archive_duration', sa.Integer(), nullable=True),
    sa.Column('archive_timestamp', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('edited_at', sa.DateTime(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=True),
    sa.Column('int_owner_id', sa.BigInteger(), nullable=True),
    sa.Column('parent_id', sa.BigInteger(), nullable=True),
    sa.Column('guild_id', sa.BigInteger(), nullable=True),
    sa.ForeignKeyConstraint(['guild_id'], ['guilds.guild_id'], ),
    sa.ForeignKeyConstraint(['int_owner_id'], ['users.int_user_id'], ),
    sa.ForeignKeyConstraint(['parent_id'], ['channels.channel_id'], ),
    sa.PrimaryKeyConstraint('thread_id')
    )
    op.create_table('thread_members',
    sa.Column('int_member_id', sa.BigInteger(), nullable=True),
    sa.Column('thread_id', sa.BigInteger(), nullable=True),
    sa.Column('joined_at', sa.DateTime(), nullable=True),
    sa.Column('left_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['int_member_id'], ['users.int_user_id'], ),
    sa.ForeignKeyConstraint(['thread_id'], ['threads.thread_id'], ),
    sa.UniqueConstraint('int_member_id', 'thread_id', 'joined_at', name='uq_thread_members')
    )


def downgrade() -> None:
    op.drop_table('thread_members')
    op.drop_table('threads')
