"""Extend auditlogaction enum

Revision ID: 74bc9658d7ff
Revises: 8c060bb0e6dc
Create Date: 2022-10-01 18:13:54.827286

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '74bc9658d7ff'
down_revision = '8c060bb0e6dc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'stage_instance_create'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'stage_instance_update'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'stage_instance_delete'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'sticker_create'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'sticker_update'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'sticker_delete'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'scheduled_event_create'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'scheduled_event_update'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'scheduled_event_delete'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'thread_create'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'thread_update'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'thread_delete'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'app_command_permission_update'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'automod_rule_create'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'automod_rule_update'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'automod_rule_delete'")
        op.execute("ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'automod_block_message'")


def downgrade() -> None:
    pass
