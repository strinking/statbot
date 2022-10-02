"""Add thread_id to messages and typing tables

Revision ID: 2b5e4f83be7e
Revises: 4ad50631992f
Create Date: 2022-10-02 01:16:37.285311

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2b5e4f83be7e'
down_revision = '4ad50631992f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('messages', 'channel_id', nullable=True)
    op.add_column('messages', sa.Column('thread_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key('messages_thread_id_fkey', 'messages', 'threads', ['thread_id'], ['thread_id'])

    op.alter_column('typing', 'channel_id', nullable=True)
    op.add_column('typing', sa.Column('thread_id', sa.BigInteger(), nullable=True))
    op.drop_constraint('uq_typing', 'typing', type_='unique')
    op.create_unique_constraint('uq_typing', 'typing', ['timestamp', 'int_user_id', 'channel_id', 'thread_id', 'guild_id'])
    op.create_foreign_key('typing_thread_id_fkey', 'typing', 'threads', ['thread_id'], ['thread_id'])


def downgrade() -> None:
    op.drop_constraint('typing_thread_id_fkey', 'typing', type_='foreignkey')
    op.drop_constraint('uq_typing', 'typing', type_='unique')
    op.create_unique_constraint('uq_typing', 'typing', ['timestamp', 'int_user_id', 'channel_id', 'guild_id'])
    op.drop_column('typing', 'thread_id')
    op.drop_constraint('messages_thread_id_fkey', 'messages', type_='foreignkey')
    op.drop_column('messages', 'thread_id')
