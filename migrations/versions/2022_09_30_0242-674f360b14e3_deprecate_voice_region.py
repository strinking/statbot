"""Deprecate voice_region

Revision ID: 674f360b14e3
Revises: initial_revision_discord_py_1_5
Create Date: 2022-09-30 02:42:34.186912

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '674f360b14e3'
down_revision = 'initial_revision_discord_py_1_5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # https://alembic.sqlalchemy.org/en/latest/api/runtime.html#alembic.runtime.migration.MigrationContext.autocommit_block
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE voiceregion ADD VALUE IF NOT EXISTS 'deprecated'")


def downgrade() -> None:
    pass
