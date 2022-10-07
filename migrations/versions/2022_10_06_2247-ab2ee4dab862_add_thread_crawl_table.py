"""Add thread_crawl table

Revision ID: ab2ee4dab862
Revises: 2b5e4f83be7e
Create Date: 2022-10-06 22:47:43.889520

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab2ee4dab862'
down_revision = '2b5e4f83be7e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('thread_crawl',
    sa.Column('thread_id', sa.BigInteger(), nullable=False),
    sa.Column('last_message_id', sa.BigInteger(), nullable=True),
    sa.ForeignKeyConstraint(['thread_id'], ['threads.thread_id'], ),
    sa.PrimaryKeyConstraint('thread_id')
    )


def downgrade() -> None:
    op.drop_table('thread_crawl')
