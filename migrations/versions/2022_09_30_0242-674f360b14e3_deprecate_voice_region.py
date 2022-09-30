"""Deprecate voice_region

Revision ID: 674f360b14e3
Revises: initial_revision
Create Date: 2022-09-30 02:42:34.186912

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '674f360b14e3'
down_revision = 'initial_revision'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("COMMIT")
    op.execute("ALTER TYPE voiceregion ADD VALUE 'deprecated'")


def downgrade() -> None:
    pass
