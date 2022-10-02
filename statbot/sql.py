#
# sql.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017-2018 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

from collections import namedtuple
from datetime import datetime
import functools
import random

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
import discord
from sqlalchemy import create_engine, and_, Column, inspect
from sqlalchemy.sql import select
from sqlalchemy.dialects.postgresql import insert as p_insert

from .audit_log import AuditLogData
from .cache import LruCache
from .emoji import EmojiData
from .mention import MentionType
from .schema import DiscordMetadata
from .util import int_hash, null_logger

Column = functools.partial(Column, nullable=False)
FakeMember = namedtuple("FakeMember", ("guild", "id"))

MAX_ID = 2**63 - 1

__all__ = [
    "DiscordSqlHandler",
]

# Value builders
def guild_values(guild):
    return {
        "guild_id": guild.id,
        "int_owner_id": int_hash(guild.owner.id),
        "name": guild.name,
        "icon": '' if guild.icon is None else guild.icon.url,
        "voice_region": "deprecated",
        "afk_channel_id": getattr(guild.afk_channel, "id", None),
        "afk_timeout": guild.afk_timeout,
        "mfa": bool(guild.mfa_level),
        "verification_level": guild.verification_level,
        "explicit_content_filter": guild.explicit_content_filter,
        "features": guild.features,
        "splash": guild.splash,
    }


def message_values(message: discord.Message, is_in_thread=False):
    if message.type == discord.MessageType.default:
        system_content = ""
    else:
        system_content = message.system_content

    attach_urls = "\n".join(attach.url for attach in message.attachments)
    if message.content:
        content = "\n".join((message.content, attach_urls))
    else:
        content = attach_urls

    return {
        "message_id": message.id,
        "created_at": message.created_at,
        "edited_at": message.edited_at,
        "deleted_at": None,
        "message_type": message.type,
        "system_content": system_content,
        "content": content.replace("\0", " "),
        "embeds": [embed.to_dict() for embed in message.embeds],
        "attachments": len(message.attachments),
        "webhook_id": message.webhook_id,
        "int_user_id": int_hash(message.author.id),
        "channel_id": message.channel.id if not is_in_thread else None,
        "thread_id": message.channel.id if is_in_thread else None,
        "guild_id": message.guild.id,
    }


def channel_values(channel):
    return {
        "channel_id": channel.id,
        "name": channel.name,
        "is_nsfw": channel.is_nsfw(),
        "is_deleted": False,
        "position": channel.position,
        "topic": channel.topic,
        "changed_roles": [role.id for role in channel.changed_roles],
        "category_id": getattr(channel.category, "id", None),
        "guild_id": channel.guild.id,
    }


def voice_channel_values(channel):
    return {
        "voice_channel_id": channel.id,
        "name": channel.name,
        "is_deleted": False,
        "position": channel.position,
        "bitrate": channel.bitrate,
        "user_limit": channel.user_limit,
        "changed_roles": [role.id for role in channel.changed_roles],
        "category_id": getattr(channel.category, "id", None),
        "guild_id": channel.guild.id,
    }


def channel_categories_values(category):
    return {
        "category_id": category.id,
        "name": category.name,
        "position": category.position,
        "is_deleted": False,
        "is_nsfw": category.is_nsfw(),
        "parent_category_id": getattr(category.category, "id", None),
        "changed_roles": [role.id for role in category.changed_roles],
        "guild_id": category.guild.id,
    }


def user_values(user, deleted=False):
    return {
        "int_user_id": int_hash(user.id),
        "real_user_id": user.id,
        "name": user.name,
        "discriminator": user.discriminator,
        "avatar": None if user.avatar is None else user.avatar.url,
        "is_deleted": deleted,
        "is_bot": user.bot,
    }


def guild_member_values(member):
    return {
        "int_user_id": int_hash(member.id),
        "guild_id": member.guild.id,
        "is_member": True,
        "joined_at": member.joined_at,
        "nick": member.nick,
    }


def role_member_values(member, role):
    return {
        "role_id": role.id,
        "guild_id": role.guild.id,
        "int_user_id": int_hash(member.id),
    }


def role_values(role):
    return {
        "role_id": role.id,
        "name": role.name,
        "color": role.color.value,
        "raw_permissions": role.permissions.value,
        "guild_id": role.guild.id,
        "is_hoisted": role.hoist,
        "is_managed": role.managed,
        "is_mentionable": role.mentionable,
        "is_deleted": False,
        "position": role.position,
    }


def reaction_values(reaction, user, current):
    data = EmojiData(reaction.emoji)
    return {
        "message_id": reaction.message.id,
        "emoji_id": data.id,
        "emoji_unicode": data.unicode,
        "int_user_id": int_hash(user.id),
        "created_at": datetime.now() if current else None,
        "deleted_at": None,
        "channel_id": reaction.message.channel.id,
        "guild_id": reaction.message.guild.id,
    }


def thread_values(thread: discord.Thread, deleted=False):
    return {
        "thread_id": thread.id,
        "name": thread.name,
        "invitable": thread.invitable,
        "locked": thread.locked,
        "archived": thread.archived,
        "auto_archive_duration": thread.auto_archive_duration,
        "archive_timestamp": thread.archive_timestamp,
        "created_at": thread.created_at,
        "edited_at": datetime.now(),
        "deleted_at": datetime.now() if deleted else None,
        "is_deleted": deleted,
        "int_owner_id": int_hash(thread.owner_id),
        "parent_id": thread.parent_id,
        "guild_id": thread.guild.id,
    }


def thread_member_values(member: discord.ThreadMember, removed=False):
    return {
        "int_member_id": int_hash(member.id),
        "thread_id": member.thread_id,
        "joined_at": member.joined_at,
        "left_at": datetime.now() if removed else None,
    }


class _Transaction:
    __slots__ = (
        "conn",
        "logger",
        "txact",
        "ok",
    )

    def __init__(self, conn, logger):
        self.conn = conn
        self.logger = logger
        self.txact = None
        self.ok = True

    def __enter__(self):
        self.logger.debug("Starting transaction...")
        self.txact = self.conn.begin()
        return self

    def __exit__(self, type, value, traceback):
        if (type, value, traceback) == (None, None, None):
            self.logger.debug("Committing transaction...")
            self.txact.commit()
        else:
            self.logger.error("Exception occurred in 'with' scope!", exc_info=1)
            self.logger.debug("Rolling back transaction...")
            self.ok = False
            self.txact.rollback()

    def execute(self, *args, **kwargs):
        return self.conn.execute(*args, **kwargs)


class DiscordSqlHandler:
    """
    An abstract handling class that bridges the gap between
    the SQLAlchemy code and the discord.py code.

    It can correctly handle discord objects and ingest or
    process them into the SQL database accordingly.
    """

    # disable because we get false positives for dml in sqlalchemy insert/delete
    # pylint: disable=no-value-for-parameter

    __slots__ = (
        "db",
        "conn",
        "logger",
        "tb_messages",
        "tb_reactions",
        "tb_typing",
        "tb_pins",
        "tb_mentions",
        "tb_guilds",
        "tb_channels",
        "tb_voice_channels",
        "tb_channel_categories",
        "tb_users",
        "tb_guild_membership",
        "tb_role_membership",
        "tb_avatar_history",
        "tb_username_history",
        "tb_nickname_history",
        "tb_emojis",
        "tb_roles",
        "tb_audit_log",
        "tb_channel_crawl",
        "tb_audit_log_crawl",
        "tb_threads",
        "tb_thread_members",
        "message_cache",
        "typing_cache",
        "guild_cache",
        "channel_cache",
        "voice_channel_cache",
        "channel_category_cache",
        "user_cache",
        "emoji_cache",
        "role_cache",
        "thread_cache",
    )

    def __init__(self, addr, cache_size, logger=null_logger):
        logger.info(f"Opening database: '{addr}'")
        self.db = create_engine(addr)
        self.conn = self.db.connect()
        meta = DiscordMetadata(self.db)
        self.logger = logger

        self.tb_messages = meta.tb_messages
        self.tb_reactions = meta.tb_reactions
        self.tb_typing = meta.tb_typing
        self.tb_pins = meta.tb_pins
        self.tb_mentions = meta.tb_mentions
        self.tb_guilds = meta.tb_guilds
        self.tb_channels = meta.tb_channels
        self.tb_voice_channels = meta.tb_voice_channels
        self.tb_channel_categories = meta.tb_channel_categories
        self.tb_users = meta.tb_users
        self.tb_guild_membership = meta.tb_guild_membership
        self.tb_role_membership = meta.tb_role_membership
        self.tb_avatar_history = meta.tb_avatar_history
        self.tb_username_history = meta.tb_username_history
        self.tb_nickname_history = meta.tb_nickname_history
        self.tb_emojis = meta.tb_emojis
        self.tb_roles = meta.tb_roles
        self.tb_audit_log = meta.tb_audit_log
        self.tb_channel_crawl = meta.tb_channel_crawl
        self.tb_audit_log_crawl = meta.tb_audit_log_crawl
        self.tb_threads = meta.tb_threads
        self.tb_thread_members = meta.tb_thread_members

        # Caches
        if cache_size is not None:
            self.message_cache = LruCache(cache_size["event-size"])
            self.typing_cache = LruCache(cache_size["event-size"])
            self.guild_cache = LruCache(cache_size["lookup-size"])
            self.channel_cache = LruCache(cache_size["lookup-size"])
            self.voice_channel_cache = LruCache(cache_size["lookup-size"])
            self.channel_category_cache = LruCache(cache_size["lookup-size"])
            self.user_cache = LruCache(cache_size["lookup-size"])
            self.emoji_cache = LruCache(cache_size["lookup-size"])
            self.role_cache = LruCache(cache_size["lookup-size"])
            self.thread_cache = LruCache(cache_size["lookup-size"])

        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", addr)
        # Don't allow Alembic to replace our logging handlers
        alembic_cfg.attributes["configure_logger"] = False

        if not inspect(self.db).has_table("messages"):
            self.logger.info("Creating tables")
            meta.metadata_obj.create_all(self.db)
            command.stamp(alembic_cfg, "head")
        else:
            self.logger.info("Performing migrations")
            migration_context = MigrationContext.configure(self.conn)
            current_rev = migration_context.get_current_revision()
            if current_rev is None:
                # This means the db is in a state prior to when Alembic
                # was added; this assumes discord.py v1.5
                command.stamp(alembic_cfg, "initial_revision_discord_py_1_5")
            command.upgrade(alembic_cfg, "head")
        self.logger.info("Created all tables.")

    # Transaction logic
    def transaction(self):
        return _Transaction(self.conn, self.logger)

    # Guild
    def upsert_guild(self, txact, guild):
        values = guild_values(guild)
        if self.guild_cache.get(guild.id) == values:
            self.logger.debug(f"Guild lookup for {guild.id} is already up-to-date")
            return

        self.logger.info(f"Updating lookup data for guild {guild.name}")
        ups = (
            p_insert(self.tb_guilds)
            .values(values)
            .on_conflict_do_update(
                index_elements=["guild_id"],
                index_where=(self.tb_guilds.c.guild_id == guild.id),
                set_=values,
            )
        )
        txact.conn.execute(ups)
        self.guild_cache[guild.id] = values

    # Messages
    def add_message(self, txact, message: discord.Message):
        is_in_thread = isinstance(message.channel, discord.Thread)

        values = message_values(message, is_in_thread)

        if self.message_cache.get(message.id) == values:
            self.logger.debug(f"Message lookup for {message.id} is already up-to-date")
            return

        if is_in_thread:
            self.upsert_thread(txact, message.channel)

        self.logger.debug(f"Inserting message {message.id}")
        ins = self.tb_messages.insert().values(values)
        txact.execute(ins)
        self.message_cache[message.id] = values

        self.upsert_user(txact, message.author)
        self.insert_mentions(txact, message)

    def edit_message(self, txact, before, after):
        self.logger.debug(f"Updating message {after.id}")
        upd = (
            self.tb_messages.update()
            .values(
                {
                    "edited_at": after.edited_at,
                    "content": after.content,
                    "embeds": [embed.to_dict() for embed in after.embeds],
                }
            )
            .where(self.tb_messages.c.message_id == after.id)
        )
        txact.execute(upd)

        self.insert_mentions(txact, after)

    def remove_message(self, txact, message):
        self.logger.debug(f"Deleting message {message.id}")
        upd = (
            self.tb_messages.update()
            .values(deleted_at=datetime.now())
            .where(self.tb_messages.c.message_id == message.id)
        )
        txact.execute(upd)
        self.message_cache.pop(message.id, None)

    def insert_message(self, txact, message: discord.Message):
        is_in_thread = isinstance(message.channel, discord.Thread)

        values = message_values(message, is_in_thread)

        if self.message_cache.get(message.id) == values:
            self.logger.debug(f"Message lookup for {message.id} is already up-to-date")
            return

        if is_in_thread:
            self.upsert_thread(txact, message.channel)

        self.logger.debug(f"Inserting message {message.id}")
        ins = (
            p_insert(self.tb_messages)
            .values(values)
            .on_conflict_do_nothing(index_elements=["message_id"])
        )
        txact.execute(ins)
        self.message_cache[message.id] = values

        self.upsert_user(txact, message.author)
        self.insert_mentions(txact, message)

    # Mentions
    def insert_mentions(self, txact, message):
        self.logger.debug(f"Inserting all mentions in message {message.id}")

        for id in message.raw_mentions:
            if id > MAX_ID:
                self.logger.error(f"User mention was too long: {id}")
                continue

            self.logger.debug(f"User mention: {id}")
            ins = (
                p_insert(self.tb_mentions)
                .values(
                    {
                        "mentioned_id": id,
                        "type": MentionType.USER,
                        "message_id": message.id,
                        "channel_id": message.channel.id,
                        "guild_id": message.guild.id,
                    }
                )
                .on_conflict_do_nothing(
                    index_elements=["mentioned_id", "type", "message_id"]
                )
            )
            txact.execute(ins)

        for id in message.raw_role_mentions:
            if id > MAX_ID:
                self.logger.error(f"Role mention was too long: {id}")
                continue

            self.logger.debug(f"Role mention: {id}")
            ins = (
                p_insert(self.tb_mentions)
                .values(
                    {
                        "mentioned_id": id,
                        "type": MentionType.ROLE,
                        "message_id": message.id,
                        "channel_id": message.channel.id,
                        "guild_id": message.guild.id,
                    }
                )
                .on_conflict_do_nothing(
                    index_elements=["mentioned_id", "type", "message_id"]
                )
            )
            txact.execute(ins)

        for id in message.raw_channel_mentions:
            if id > MAX_ID:
                self.logger.error(f"Channel mention was too long: {id}")
                continue

            self.logger.debug(f"Channel mention: {id}")
            ins = (
                p_insert(self.tb_mentions)
                .values(
                    {
                        "mentioned_id": id,
                        "type": MentionType.CHANNEL,
                        "message_id": message.id,
                        "channel_id": message.channel.id,
                        "guild_id": message.guild.id,
                    }
                )
                .on_conflict_do_nothing(
                    index_elements=["mentioned_id", "type", "message_id"]
                )
            )
            txact.execute(ins)

    # Typing
    def typing(self, txact, channel, user, when):
        key = (when, user.id, channel.id)
        if self.typing_cache.get(key, False):
            self.logger.debug("Typing lookup is up-to-date")
            return

        is_in_thread = isinstance(channel, discord.Thread)

        if is_in_thread:
            self.upsert_thread(txact, channel)

        self.logger.debug(f"Inserting typing event for user {user.id}")
        ins = self.tb_typing.insert().values(
            {
                "timestamp": when,
                "int_user_id": int_hash(user.id),
                "channel_id": channel.id if not is_in_thread else None,
                "thread_id": channel.id if is_in_thread else None,
                "guild_id": channel.guild.id,
            }
        )
        txact.execute(ins)
        self.typing_cache[key] = True

    # Reactions
    def add_reaction(self, txact, reaction, user):
        self.logger.debug(
            f"Inserting live reaction for user {user.id} on message {reaction.message.id}"
        )
        self.upsert_emoji(txact, reaction.emoji)
        self.upsert_user(txact, user)
        values = reaction_values(reaction, user, True)
        ins = self.tb_reactions.insert().values(values)
        txact.execute(ins)

    def remove_reaction(self, txact, reaction, user):
        self.logger.debug(
            f"Deleting reaction for user {user.id} on message {reaction.message.id}"
        )
        data = EmojiData(reaction.emoji)
        upd = (
            self.tb_reactions.update()
            .values(deleted_at=datetime.now())
            .where(self.tb_reactions.c.message_id == reaction.message.id)
            .where(self.tb_reactions.c.emoji_id == data.id)
            .where(self.tb_reactions.c.emoji_unicode == data.unicode)
            .where(self.tb_reactions.c.int_user_id == int_hash(user.id))
        )
        txact.execute(upd)

    def insert_reaction(self, txact, reaction, users):
        self.logger.debug(f"Inserting past reactions for {reaction.message.id}")
        self.upsert_emoji(txact, reaction.emoji)
        data = EmojiData(reaction.emoji)
        for user in users:
            self.upsert_user(txact, user)
            values = reaction_values(reaction, user, False)
            self.logger.debug(f"Inserting single reaction {data} from {user.id}")
            ins = (
                p_insert(self.tb_reactions)
                .values(values)
                .on_conflict_do_nothing(
                    index_elements=[
                        "message_id",
                        "emoji_id",
                        "emoji_unicode",
                        "int_user_id",
                        "created_at",
                    ]
                )
            )
            txact.execute(ins)

    def clear_reactions(self, txact, message):
        self.logger.debug(f"Deleting all reactions on message {message.id}")
        upd = (
            self.tb_reactions.update()
            .values(deleted_at=datetime.now())
            .where(self.tb_reactions.c.message_id == message.id)
        )
        txact.execute(upd)

    # Pins (TODO)
    def add_pin(self, txact, announce, message):
        # pylint: disable=unreachable
        raise NotImplementedError

        self.logger.debug(f"Inserting pin for message {message.id}")
        ins = self.tb_pins.insert().values(
            {
                "pin_id": announce.id,
                "message_id": message.id,
                "pinner_id": announce.author.id,
                "int_user_id": int_hash(message.author.id),
                "channel_id": message.channel.id,
                "guild_id": message.guild.id,
            }
        )
        txact.execute(ins)

    def remove_pin(self, txact, announce, message):
        # pylint: disable=unreachable
        raise NotImplementedError

        self.logger.debug(f"Deleting pin for message {message.id}")
        delet = (
            self.tb_pins.delete()
            .where(self.tb_pins.c.pin_id == announce.id)
            .where(self.tb_pins.c.message_id == message.id)
        )
        txact.execute(delet)

    # Roles
    def add_role(self, txact, role):
        if role.id in self.role_cache:
            self.logger.debug(f"Role {role.id} already inserted.")
            return

        self.logger.info(f"Inserting role {role.id}")
        values = role_values(role)
        ins = self.tb_roles.insert().values(values)
        txact.execute(ins)
        self.role_cache[role.id] = values

    def _update_role(self, txact, role):
        self.logger.info(f"Updating role {role.id} in guild {role.guild.id}")
        values = role_values(role)
        upd = (
            self.tb_roles.update()
            .where(self.tb_roles.c.role_id == role.id)
            .values(values)
        )
        txact.execute(upd)
        self.role_cache[role.id] = values

    def update_role(self, txact, role):
        if role.id in self.role_cache:
            self._update_role(txact, role)
        else:
            self.upsert_role(txact, role)

    def remove_role(self, txact, role):
        self.logger.info(f"Deleting role {role.id}")
        upd = (
            self.tb_roles.update()
            .values(is_deleted=True)
            .where(self.tb_roles.c.role_id == role.id)
        )
        txact.execute(upd)
        self.role_cache.pop(role.id, None)

    def upsert_role(self, txact, role):
        values = role_values(role)
        if self.role_cache.get(role.id) == values:
            self.logger.debug(f"Role lookup for {role.id} is already up-to-date")
            return

        self.logger.debug(f"Updating lookup data for role {role.name}")
        ups = (
            p_insert(self.tb_roles)
            .values(values)
            .on_conflict_do_update(
                index_elements=["role_id"],
                index_where=(self.tb_roles.c.role_id == role.id),
                set_=values,
            )
        )
        txact.execute(ups)
        self.role_cache[role.id] = values

    # Channels
    def add_channel(self, txact, channel):
        if channel.id in self.channel_cache:
            self.logger.debug(f"Channel {channel.id} already inserted.")
            return

        self.logger.info(
            f"Inserting new channel {channel.id} for guild {channel.guild.id}"
        )
        values = channel_values(channel)
        ins = self.tb_channels.insert().values(values)
        txact.execute(ins)
        self.channel_cache[channel.id] = values

    def _update_channel(self, txact, channel):
        self.logger.info(f"Updating channel {channel.id} in guild {channel.guild.id}")
        values = channel_values(channel)
        upd = (
            self.tb_channels.update()
            .where(self.tb_channels.c.channel_id == channel.id)
            .values(values)
        )
        txact.execute(upd)
        self.channel_cache[channel.id] = values

    def update_channel(self, txact, channel):
        if channel.id in self.channel_cache:
            self._update_channel(txact, channel)
        else:
            self.upsert_channel(txact, channel)

    def remove_channel(self, txact, channel):
        self.logger.info(f"Deleting channel {channel.id} in guild {channel.guild.id}")
        upd = (
            self.tb_channels.update()
            .values(is_deleted=True)
            .where(self.tb_channels.c.channel_id == channel.id)
        )
        txact.execute(upd)
        self.channel_cache.pop(channel.id, None)

    def upsert_channel(self, txact, channel):
        values = channel_values(channel)
        if self.channel_cache.get(channel.id) == values:
            self.logger.debug(f"Channel lookup for {channel.id} is already up-to-date")
            return

        self.logger.debug(f"Updating lookup data for channel #{channel.name}")
        ups = (
            p_insert(self.tb_channels)
            .values(values)
            .on_conflict_do_update(
                index_elements=["channel_id"],
                index_where=(self.tb_channels.c.channel_id == channel.id),
                set_=values,
            )
        )
        txact.execute(ups)
        self.channel_cache[channel.id] = values

    # Voice Channels
    def add_voice_channel(self, txact, channel):
        if channel in self.voice_channel_cache:
            self.logger.debug(f"Voice channel {channel.id} already inserted")
            return

        self.logger.info(
            "Inserting new voice channel {channel.id} for guild {channel.guild.id}"
        )
        values = voice_channel_values(channel)
        ins = self.tb_voice_channels.insert().values(values)
        txact.execute(ins)
        self.voice_channel_cache[channel.id] = values

    def _update_voice_channel(self, txact, channel):
        self.logger.info(
            f"Updating voice channel {channel.id} in guild {channel.guild.id}"
        )
        values = voice_channel_values(channel)
        upd = (
            self.tb_voice_channels.update()
            .where(self.tb_voice_channels.c.voice_channel_id == channel.id)
            .values(values)
        )
        txact.execute(upd)
        self.voice_channel_cache[channel.id] = values

    def update_voice_channel(self, txact, channel):
        if channel.id in self.voice_channel_cache:
            self._update_voice_channel(txact, channel)
        else:
            self.upsert_channel(txact, channel)

    def remove_voice_channel(self, txact, channel):
        self.logger.info(
            f"Deleting voice channel {channel.id} in guild {channel.guild.id}"
        )
        upd = (
            self.tb_voice_channels.update()
            .values(is_deleted=True)
            .where(self.tb_voice_channels.c.voice_channel_id == channel.id)
        )
        txact.execute(upd)
        self.voice_channel_cache.pop(channel.id, None)

    def upsert_voice_channel(self, txact, channel):
        values = voice_channel_values(channel)
        if self.voice_channel_cache.get(channel.id) == values:
            self.logger.debug(
                f"Voice channel lookup for {channel.id} is already up-to-date"
            )
            return

        self.logger.debug(f"Updating lookup data for voice channel '{channel.name}'")
        ups = (
            p_insert(self.tb_voice_channels)
            .values(values)
            .on_conflict_do_update(
                index_elements=["voice_channel_id"],
                index_where=(self.tb_voice_channels.c.voice_channel_id == channel.id),
                set_=values,
            )
        )
        txact.execute(ups)
        self.voice_channel_cache[channel.id] = values

    # Channel Categories
    def add_channel_category(self, txact, category):
        if category.id in self.channel_category_cache:
            self.logger.debug(f"Channel category {category.id} already inserted.")
            return

        self.logger.info(
            f"Inserting new category {category.id} for guild {category.guild.id}"
        )
        values = channel_categories_values(category)
        ins = self.tb_channel_categories.insert().values(values)
        txact.execute(ins)
        self.channel_category_cache[category.id] = values

    def _update_channel_category(self, txact, category):
        self.logger.info(
            f"Updating channel category {category.id} in guild {category.guild.id}"
        )
        values = channel_categories_values(category)
        upd = (
            self.tb_channel_categories.update()
            .where(self.tb_channel_categories.c.category_id == category.id)
            .values(values)
        )
        txact.execute(upd)
        self.channel_category_cache[category.id] = values

    def update_channel_category(self, txact, category):
        if category.id in self.channel_category_cache:
            self._update_channel_category(txact, category)
        else:
            self.upsert_channel_category(txact, category)

    def remove_channel_category(self, txact, category):
        self.logger.info(
            f"Deleting channel category {category.id} in guild {category.guild.id}"
        )
        upd = (
            self.tb_channel_categories.update()
            .values(is_deleted=True)
            .where(self.tb_channels.c.category_id == category.id)
        )
        txact.execute(upd)
        self.channel_category_cache.pop(category.id, None)

    def upsert_channel_category(self, txact, category):
        values = channel_categories_values(category)
        if self.channel_cache.get(category.id) == values:
            self.logger.debug(
                f"Channel category lookup for {category.id} is already up-to-date"
            )
            return

        self.logger.debug(f"Updating lookup data for channel category {category.name}")
        ups = (
            p_insert(self.tb_channel_categories)
            .values(values)
            .on_conflict_do_update(
                index_elements=["category_id"],
                index_where=(self.tb_channel_categories.c.category_id == category.id),
                set_=values,
            )
        )
        txact.execute(ups)
        self.channel_category_cache[category.id] = values

    # Users
    def add_user(self, txact, user):
        if user.id in self.user_cache:
            self.logger.debug(f"User {user.id} already inserted.")
            return

        self.logger.debug(f"Inserting user {user.id}")
        values = user_values(user)
        ins = self.tb_users.insert().values(values)
        txact.execute(ins)
        self.user_cache[user.id] = values

    def _update_user(self, txact, user):
        self.logger.debug(f"Updating user {user.id}")
        values = user_values(user)
        upd = (
            self.tb_users.update()
            .where(self.tb_users.c.int_user_id == int_hash(user.id))
            .values(values)
        )
        txact.execute(upd)
        self.user_cache[user.id] = values

    def update_user(self, txact, user):
        if user.id in self.user_cache:
            self._update_user(txact, user)
        else:
            self.upsert_user(txact, user)

    def remove_user(self, txact, user):
        self.logger.debug(f"Removing user {user.id}")
        upd = (
            self.tb_users.update()
            .values(is_deleted=True)
            .where(self.tb_users.c.int_user_id == int_hash(user.id))
        )
        txact.execute(upd)
        self.user_cache.pop(user.id, None)

    def upsert_user(self, txact, user):
        self.logger.debug(f"Upserting user {user.id}")
        values = user_values(user)
        if self.user_cache.get(user.id) == values:
            self.logger.debug(f"User lookup for {user.id} is already up-to-date")
            return

        ups = (
            p_insert(self.tb_users)
            .values(values)
            .on_conflict_do_update(
                index_elements=["int_user_id"],
                index_where=(self.tb_users.c.int_user_id == int_hash(user.id)),
                set_=values,
            )
        )
        txact.execute(ups)
        self.user_cache[user.id] = values

    # Members
    def update_member(self, txact, member):
        self.logger.debug(f"Updating member data for {member.id}")
        upd = (
            self.tb_guild_membership.update()
            .where(
                and_(
                    self.tb_guild_membership.c.int_user_id == int_hash(member.id),
                    self.tb_guild_membership.c.guild_id == member.guild.id,
                )
            )
            .values(nick=member.nick)
        )
        txact.execute(upd)

        self._delete_role_membership(txact, member)
        self._insert_role_membership(txact, member)

    def _delete_role_membership(self, txact, member):
        delet = self.tb_role_membership.delete().where(
            and_(
                self.tb_role_membership.c.int_user_id == int_hash(member.id),
                self.tb_role_membership.c.guild_id == member.guild.id,
                self.tb_role_membership.c.role_id not in member.roles,
            )
        )
        txact.execute(delet)

    def _insert_role_membership(self, txact, member):
        for role in member.roles:
            values = role_member_values(member, role)
            ins = self.tb_role_membership.insert().values(values)
            txact.execute(ins)

    def remove_member(self, txact, member):
        self.logger.debug(f"Removing member {member.id} from guild {member.guild.id}")
        upd = (
            self.tb_guild_membership.update()
            .where(
                and_(
                    self.tb_guild_membership.c.int_user_id == int_hash(member.id),
                    self.tb_guild_membership.c.guild_id == member.guild.id,
                )
            )
            .values(is_member=False)
        )
        txact.execute(upd)

        # Don't delete role membership

    def remove_old_members(self, txact, guild):
        # Since pylint complains about <thing> == True.
        # We need to do this otherwise silly comparison
        # because it's not a comparison at all, it's actually
        # creating a SQLAlchemy "equality" object that is used
        # to generate the query.
        #
        # pylint: disable=singleton-comparison

        self.logger.debug(f"Deleting old members from guild {guild.name}")
        sel = select([self.tb_guild_membership]).where(
            and_(
                self.tb_guild_membership.c.guild_id == guild.id,
                self.tb_guild_membership.c.is_member == True,
            )
        )
        result = txact.execute(sel)

        for row in result.fetchall():
            user_id = row[0]
            member = guild.get_member(user_id)
            if member is None:
                self.remove_member(txact, FakeMember(id=int_hash(user_id), guild=guild))

    def upsert_member(self, txact, member):
        self.logger.debug(f"Upserting member data for {member.id}")
        values = guild_member_values(member)
        ups = (
            p_insert(self.tb_guild_membership)
            .values(values)
            .on_conflict_do_update(
                constraint="uq_guild_membership",
                set_=values,
            )
        )
        txact.execute(ups)

        self._delete_role_membership(txact, member)
        self._insert_role_membership(txact, member)

    # User alias information
    def add_avatar(self, txact, user, timestamp, avatar, ext):
        self.logger.debug("Adding user avatar update for '%s' (%d)", user.name, user.id)
        ins = self.tb_avatar_history.insert().values(
            user_id=user.id,
            timestamp=timestamp,
            avatar=avatar.getbuffer().tobytes(),
            avatar_ext=ext,
        )
        txact.execute(ins)

    def add_username(self, txact, user, timestamp, username):
        self.logger.debug(
            "Adding username update for '%s', now '%s' (%d)",
            user.name,
            username,
            user.id,
        )
        ins = self.tb_username_history.insert().values(
            user_id=user.id, timestamp=timestamp, username=username
        )
        txact.execute(ins)

    def add_nickname(self, txact, user, timestamp, nickname):
        self.logger.debug(
            "Adding nickname update for '%s', now '%s' (%d)",
            user.display_name,
            nickname,
            user.id,
        )
        ins = self.tb_nickname_history.insert().values(
            user_id=user.id, timestamp=timestamp, nickname=nickname
        )
        txact.execute(ins)

    # Emojis
    def add_emoji(self, txact, emoji):
        data = EmojiData(emoji)
        if data.cache_id in self.emoji_cache:
            self.logger.debug(f"Emoji {data} already inserted.")
            return

        self.logger.info(f"Inserting emoji {data}")
        values = emoji.values()
        ins = self.tb_emojis.insert().values(values)
        txact.execute(ins)
        self.emoji_cache[data.cache_id] = values

    def remove_emoji(self, txact, emoji):
        data = EmojiData(emoji)
        self.logger.info(f"Deleting emoji {data}")

        upd = (
            self.tb_emojis.update()
            .values(is_deleted=True)
            .where(self.tb_emojis.c.emoji_id == data.id)
            .where(self.tb_emojis.c.emoji_unicode == data.unicode)
        )
        txact.execute(upd)
        self.emoji_cache.pop(data.cache_id, None)

    def upsert_emoji(self, txact, emoji):
        data = EmojiData(emoji)
        values = data.values()
        if self.emoji_cache.get(data.cache_id) == values:
            self.logger.debug(f"Emoji lookup for {data} is already up-to-date")
            return

        self.logger.debug(f"Upserting emoji {data}")
        ups = (
            p_insert(self.tb_emojis)
            .values(values)
            .on_conflict_do_update(
                index_elements=["emoji_id", "emoji_unicode"],
                index_where=and_(
                    self.tb_emojis.c.emoji_id == data.id,
                    self.tb_emojis.c.emoji_unicode == data.unicode,
                ),
                set_=values,
            )
        )
        txact.execute(ups)
        self.emoji_cache[data.cache_id] = values

    # Audit log
    def insert_audit_log_entry(self, txact, guild, entry):
        self.logger.debug(f"Inserting audit log entry {entry.id} from {guild.name}")
        data = AuditLogData(entry, guild)
        values = data.values()
        ins = (
            p_insert(self.tb_audit_log)
            .values(values)
            .on_conflict_do_nothing(index_elements=["audit_entry_id"])
        )
        txact.execute(ins)

    # Crawling history
    def lookup_channel_crawl(self, txact, channel):
        self.logger.info(
            f"Looking up channel crawl progress for {channel.guild.name} #{channel.name}"
        )
        sel = select([self.tb_channel_crawl]).where(
            self.tb_channel_crawl.c.channel_id == channel.id
        )
        result = txact.execute(sel)

        if result.rowcount:
            _, last_id = result.fetchone()
            return last_id
        else:
            return None

    def insert_channel_crawl(self, txact, channel, last_id):
        self.logger.info(
            f"Inserting new channel crawl progress for {channel.guild.name} #{channel.name}"
        )

        ins = self.tb_channel_crawl.insert().values(
            {
                "channel_id": channel.id,
                "last_message_id": last_id,
            }
        )
        txact.execute(ins)

    def update_channel_crawl(self, txact, channel, last_id):
        self.logger.info(
            f"Updating channel crawl progress for {channel.guild.name} #{channel.name}: {last_id}"
        )

        upd = (
            self.tb_channel_crawl.update()
            .values(last_message_id=last_id)
            .where(self.tb_channel_crawl.c.channel_id == channel.id)
        )
        txact.execute(upd)

    def delete_channel_crawl(self, txact, channel):
        self.logger.info(
            f"Deleting channel crawl progress for {channel.guild.name} #{channel.name}"
        )

        delet = self.tb_channel_crawl.delete().where(
            self.tb_channel_crawl.c.channel_id == channel.id
        )
        txact.execute(delet)

    def lookup_audit_log_crawl(self, txact, guild):
        self.logger.info(f"Looking for audit log crawl progress for {guild.name}")
        sel = select([self.tb_audit_log_crawl]).where(
            self.tb_audit_log_crawl.c.guild_id == guild.id
        )
        result = txact.execute(sel)

        if result.rowcount:
            _, last_id = result.fetchone()
            return last_id
        else:
            return None

    def insert_audit_log_crawl(self, txact, guild, last_id):
        self.logger.info(f"Inserting new audit log crawl progress for {guild.name}")

        ins = self.tb_audit_log_crawl.insert().values(
            {
                "guild_id": guild.id,
                "last_audit_entry_id": last_id,
            }
        )
        txact.execute(ins)

    def update_audit_log_crawl(self, txact, guild, last_id):
        self.logger.info(f"Updating audit log crawl progress for {guild.name}")

        upd = (
            self.tb_audit_log_crawl.update()
            .values(last_audit_entry_id=last_id)
            .where(self.tb_audit_log_crawl.c.guild_id == guild.id)
        )
        txact.execute(upd)

    def delete_audit_log_crawl(self, txact, guild):
        self.logger.info(f"Delete audit log crawl progress for {guild.name}")

        delet = self.tb_audit_log_crawl.delete().where(
            self.tb_audit_log_crawl.c.guild_id == guild.id
        )
        txact.execute(delet)

    # Threads
    def add_thread(self, txact, thread: discord.Thread):
        if thread in self.thread_cache:
            self.logger.debug(f"Thread {thread.id} already inserted")
            return

        self.logger.info(
            f"Inserting new thread {thread.id} for guild {thread.guild.id}"
        )
        values = thread_values(thread)
        ins = self.tb_threads.insert().values(values)
        txact.execute(ins)
        self.thread_cache[thread.id] = values

    def _update_thread(self, txact, thread: discord.Thread):
        self.logger.info(f"Updating thread {thread.id} in guild {thread.guild.id}")
        values = thread_values(thread)
        upd = (
            self.tb_threads.update()
            .where(self.tb_threads.c.thread_id == thread.id)
            .values(values)
        )
        txact.execute(upd)
        self.thread_cache[thread.id] = values

    def update_thread(self, txact, thread: discord.Thread):
        if thread.id in self.thread_cache:
            self._update_thread(txact, thread)
        else:
            self.upsert_thread(txact, thread)

    def remove_thread(self, txact, thread: discord.Thread):
        self.logger.info(f"Deleting thread {thread.id} in guild {thread.guild.id}")
        upd = (
            self.tb_threads.update()
            .values(is_deleted=True)
            .where(self.tb_threads.c.thread_id == thread.id)
        )
        txact.execute(upd)
        self.thread_cache.pop(thread.id, None)

    def upsert_thread(self, txact, thread: discord.Thread):
        values = thread_values(thread)
        if self.thread_cache.get(thread.id) == values:
            self.logger.debug(f"Thread lookup for {thread.id} is already up-to-date")
            return

        self.logger.debug(f"Updating lookup data for thread #{thread.name}")
        ups = (
            p_insert(self.tb_threads)
            .values(values)
            .on_conflict_do_update(
                index_elements=["thread_id"],
                index_where=(self.tb_threads.c.thread_id == thread.id),
                set_=values,
            )
        )
        txact.execute(ups)
        self.thread_cache[thread.id] = values

    # Thread Members
    def add_thread_member(self, txact, member: discord.ThreadMember):
        self.logger.debug(
            f"Inserting thread member {member.id} for thread {member.thread_id}"
        )
        values = thread_member_values(member)
        ins = self.tb_thread_members.insert().values(values)
        txact.execute(ins)

    def remove_thread_member(self, txact, member: discord.ThreadMember):
        self.logger.debug(
            f"Removing thread member {member.id} for thread {member.thread_id}"
        )
        upd = (
            self.tb_thread_members.update()
            .values(left_at=datetime.now())
            .where(self.tb_thread_members.c.int_member_id == member.id)
            .where(self.tb_thread_members.c.thread_id == member.thread_id)
            .where(self.tb_thread_members.c.left_at == None)
        )
        txact.execute(upd)

    # Privacy operations
    def privacy_scrub(self, user):
        self.logger.info(f"Scrubbing user {user.name} for privacy reasons")

        upd = (
            self.tb_users.update()
            .values(
                real_user_id=0,
                name=f"Removed for legal reasons - {random.getrandbits(24):06x}",
                discriminator=0000,
                avatar="00000000000000000000000000000000",
            )
            .where(self.tb_users.c.real_user_id == user.id)
        )

        with self.transaction() as txact:
            txact.execute(upd)
