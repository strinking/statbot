"""Add audit log types

Revision ID: 463c152f30aa
Revises: ab2ee4dab862
Create Date: 2023-03-08 20:55:08.357126

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '463c152f30aa'
down_revision = 'ab2ee4dab862'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'automod_flag_message'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'automod_timeout_member'")


def downgrade() -> None:
    pass
