"""Extend messagetype enum

Revision ID: 8c060bb0e6dc
Revises: 674f360b14e3
Create Date: 2022-10-01 12:29:46.681282

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c060bb0e6dc'
down_revision = '674f360b14e3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # https://alembic.sqlalchemy.org/en/latest/api/runtime.html#alembic.runtime.migration.MigrationContext.autocommit_block
    with op.get_context().autocommit_block():
        # added in discord.py v1.7
        op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'guild_stream'")
        op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'guild_discovery_disqualified'")
        op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'guild_discovery_requalified'")
        op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'guild_discovery_grace_period_initial_warning'")
        op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'guild_discovery_grace_period_final_warning'")

        # added in discord.py v2.0
        op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'thread_created'")
        op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'reply'")
        op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'chat_input_command'")
        op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'thread_starter_message'")
        op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'guild_invite_reminder'")
        op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'context_menu_command'")
        op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'auto_moderation_action'")


def downgrade() -> None:
    pass
