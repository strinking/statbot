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

from collections import defaultdict
from datetime import datetime
import functools

import discord
from sqlalchemy import create_engine, and_
from sqlalchemy import ARRAY, Boolean, BigInteger, Column, DateTime, Enum
from sqlalchemy import Integer, JSON, SmallInteger, String, Table, Unicode, UnicodeText
from sqlalchemy import ForeignKey, MetaData, UniqueConstraint
from sqlalchemy.sql import select
from sqlalchemy.dialects.postgresql import insert as p_insert

from .audit_log import AuditLogData
from .cache import LruCache
from .emoji import EmojiData
from .mention import MentionType
from .util import null_logger

Column = functools.partial(Column, nullable=False)

MAX_ID = 2 ** 63 - 1

__all__ = [
    'DiscordSqlHandler',
]

# Value builders
def guild_values(guild):
    return {
        'guild_id': guild.id,
        'owner_id': guild.owner.id,
        'name': guild.name,
        'icon': guild.icon,
        'voice_region': guild.region,
        'afk_channel_id': getattr(guild.afk_channel, 'id', None),
        'afk_timeout': guild.afk_timeout,
        'mfa': bool(guild.mfa_level),
        'verification_level': guild.verification_level,
        'explicit_content_filter': guild.explicit_content_filter,
        'features': guild.features,
        'splash': guild.splash,
    }

def message_values(message):
    if message.type == discord.MessageType.default:
        system_content = ''
    else:
        system_content = message.system_content

    attach_urls = '\n'.join(attach.url for attach in message.attachments)
    if message.content:
        content = '\n'.join((message.content, attach_urls))
    else:
        content = attach_urls

    return {
        'message_id': message.id,
        'created_at': message.created_at,
        'edited_at': message.edited_at,
        'deleted_at': None,
        'message_type': message.type,
        'system_content': system_content,
        'content': content.replace('\0', ' '),
        'embeds': [embed.to_dict() for embed in message.embeds],
        'attachments': len(message.attachments),
        'webhook_id': message.webhook_id,
        'user_id': message.author.id,
        'channel_id': message.channel.id,
        'guild_id': message.guild.id,
    }

def channel_values(channel):
    return {
        'channel_id': channel.id,
        'name': channel.name,
        'is_nsfw': channel.is_nsfw(),
        'is_deleted': False,
        'position': channel.position,
        'topic': channel.topic,
        'changed_roles': [role.id for role in channel.changed_roles],
        'category_id': getattr(channel.category, 'id', None),
        'guild_id': channel.guild.id,
    }

def voice_channel_values(channel):
    return {
        'voice_channel_id': channel.id,
        'name': channel.name,
        'is_deleted': False,
        'position': channel.position,
        'bitrate': channel.bitrate,
        'user_limit': channel.user_limit,
        'changed_roles': [role.id for role in channel.changed_roles],
        'category_id': getattr(channel.category, 'id', None),
        'guild_id': channel.guild.id,
    }

def channel_categories_values(category):
    return {
        'category_id': category.id,
        'name': category.name,
        'position': category.position,
        'is_deleted': False,
        'is_nsfw': category.is_nsfw(),
        'parent_category_id': getattr(category.category, 'id', None),
        'changed_roles': [role.id for role in category.changed_roles],
        'guild_id': category.guild.id,
    }

def user_values(user, deleted=False):
    return {
        'user_id': user.id,
        'name': user.name,
        'discriminator': user.discriminator,
        'avatar': user.avatar,
        'is_deleted': deleted,
        'is_bot': user.bot,
    }

def guild_member_values(member):
    return {
        'user_id': member.id,
        'guild_id': member.guild.id,
        'is_member': True,
        'joined_at': member.joined_at,
        'nick': member.nick,
    }

def role_member_values(member, role):
    return {
        'role_id': role.id,
        'guild_id': role.guild.id,
        'user_id': member.id,
    }

def role_values(role):
    return {
        'role_id': role.id,
        'name': role.name,
        'color': role.color.value,
        'raw_permissions': role.permissions.value,
        'guild_id': role.guild.id,
        'is_hoisted': role.hoist,
        'is_managed': role.managed,
        'is_mentionable': role.mentionable,
        'is_deleted': False,
        'position': role.position,
    }

def reaction_values(reaction, user, current):
    data = EmojiData(reaction.emoji)
    return {
        'message_id': reaction.message.id,
        'emoji_id': data.id,
        'emoji_unicode': data.unicode,
        'user_id': user.id,
        'created_at': datetime.now() if current else None,
        'deleted_at': None,
        'channel_id': reaction.message.channel.id,
        'guild_id': reaction.message.guild.id,
    }

def activity_values(member, when):
    values = defaultdict(lambda: None,
        timestamp=when,
        user_id=member.id,
        other={},
    )

    if member.activity is not None:
        values.update(
            type=member.activity.type,
            start_time=member.activity.start,
            end_time=member.activity.end,
        )

        for attr in ('url', 'state', 'details', 'twitch_name'):
            values[attr] = getattr(member.activity, attr, None)

        for attr in ('timestamps', 'assets', 'party'):
            values['other'][attr] = getattr(member.activity, 'assets', None)

    return values

class _Transaction:
    __slots__ = (
        'conn',
        'logger',
        'trans',
        'ok',
    )

    def __init__(self, conn, logger):
        self.conn = conn
        self.logger = logger
        self.trans = None
        self.ok = True

    def __enter__(self):
        self.logger.debug("Starting transaction...")
        self.trans = self.conn.begin()
        return self

    def __exit__(self, type, value, traceback):
        if (type, value, traceback) == (None, None, None):
            self.logger.debug("Committing transaction...")
            self.trans.commit()
        else:
            self.logger.error("Exception occurred in 'with' scope!", exc_info=1)
            self.logger.debug("Rolling back transaction...")
            self.ok = False
            self.trans.rollback()

    def execute(self, *args, **kwargs):
        return self.conn.execute(*args, **kwargs)

class DiscordSqlHandler:
    '''
    An abstract handling class that bridges the gap between
    the SQLAlchemy code and the discord.py code.

    It can correctly handle discord objects and ingest or
    process them into the SQL database accordingly.
    '''

    # disable because we get false positives for dml in sqlalchemy insert/delete
    # pylint: disable=no-value-for-parameter

    __slots__ = (
        'db',
        'conn',
        'logger',

        'tb_messages',
        'tb_reactions',
        'tb_typing',
        'tb_status',
        'tb_activities',
        'tb_pins',
        'tb_mentions',
        'tb_guilds',
        'tb_channels',
        'tb_voice_channels',
        'tb_channel_categories',
        'tb_users',
        'tb_guild_membership',
        'tb_role_membership',
        'tb_emojis',
        'tb_roles',
        'tb_audit_log',
        'tb_channel_crawl',
        'tb_audit_log_crawl',

        'message_cache',
        'typing_cache',
        'status_cache',
        'activity_cache',
        'guild_cache',
        'channel_cache',
        'voice_channel_cache',
        'channel_category_cache',
        'user_cache',
        'emoji_cache',
        'role_cache',
    )

    def __init__(self, addr, cache_size, logger=null_logger):
        logger.info(f"Opening database: '{addr}'")
        self.db = create_engine(addr)
        self.conn = self.db.connect()
        meta = MetaData(self.db)
        self.logger = logger

        self.tb_messages = Table('messages', meta,
                Column('message_id', BigInteger, primary_key=True),
                Column('created_at', DateTime),
                Column('edited_at', DateTime, nullable=True),
                Column('deleted_at', DateTime, nullable=True),
                Column('message_type', Enum(discord.MessageType)),
                Column('system_content', UnicodeText),
                Column('content', UnicodeText),
                Column('embeds', JSON),
                Column('attachments', SmallInteger),
                Column('webhook_id', BigInteger, nullable=True),
                Column('user_id', BigInteger),
                Column('channel_id', BigInteger, ForeignKey('channels.channel_id')),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')))
        self.tb_reactions = Table('reactions', meta,
                Column('message_id', BigInteger),
                Column('emoji_id', BigInteger),
                Column('emoji_unicode', Unicode(7)),
                Column('user_id', BigInteger, ForeignKey('users.user_id')),
                Column('created_at', DateTime, nullable=True),
                Column('deleted_at', DateTime, nullable=True),
                Column('channel_id', BigInteger, ForeignKey('channels.channel_id')),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')),
                UniqueConstraint('message_id', 'emoji_id', 'emoji_unicode',
                    'user_id', 'created_at', name='uq_reactions'))
        self.tb_typing = Table('typing', meta,
                Column('timestamp', DateTime),
                Column('user_id', BigInteger, ForeignKey('users.user_id')),
                Column('channel_id', BigInteger, ForeignKey('channels.channel_id')),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')),
                UniqueConstraint('timestamp', 'user_id', 'channel_id', 'guild_id',
                    name='uq_typing'))
        self.tb_status = Table('status', meta,
                Column('timestamp', DateTime),
                Column('user_id', BigInteger, ForeignKey('users.user_id')),
                Column('status', Enum(discord.Status)),
                UniqueConstraint('timestamp', 'user_id', name='uq_status'))
        self.tb_activities = Table('activities', meta,
                Column('timestamp', DateTime),
                Column('user_id', BigInteger, ForeignKey('users.user_id')),
                Column('type', Enum(discord.ActivityType), nullable=True),
                Column('name', String, nullable=True),
                Column('start_time', DateTime, nullable=True),
                Column('end_time', DateTime, nullable=True),
                Column('url', String, nullable=True),
                Column('state', String, nullable=True),
                Column('details', String, nullable=True),
                Column('twitch_name', String, nullable=True),
                Column('other', JSON),
                UniqueConstraint('timestamp', 'user_id', name='uq_activities'))
        self.tb_pins = Table('pins', meta,
                Column('pin_id', BigInteger, primary_key=True),
                Column('message_id', BigInteger, ForeignKey('messages.message_id'),
                    primary_key=True),
                Column('pinner_id', BigInteger, ForeignKey('users.user_id')),
                Column('user_id', BigInteger, ForeignKey('users.user_id')),
                Column('channel_id', BigInteger, ForeignKey('channels.channel_id')),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')))
        self.tb_mentions = Table('mentions', meta,
                Column('mentioned_id', BigInteger, primary_key=True),
                Column('type', Enum(MentionType), primary_key=True),
                Column('message_id', BigInteger, ForeignKey('messages.message_id'), primary_key=True),
                Column('channel_id', BigInteger, ForeignKey('channels.channel_id')),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')),
                UniqueConstraint('mentioned_id', 'type', 'message_id', name='uq_mention'))
        self.tb_guilds = Table('guilds', meta,
                Column('guild_id', BigInteger, primary_key=True),
                Column('owner_id', BigInteger, ForeignKey('users.user_id')),
                Column('name', Unicode),
                Column('icon', String),
                Column('voice_region', Enum(discord.VoiceRegion)),
                Column('afk_channel_id', BigInteger, nullable=True),
                Column('afk_timeout', Integer),
                Column('mfa', Boolean),
                Column('verification_level', Enum(discord.VerificationLevel)),
                Column('explicit_content_filter', Enum(discord.ContentFilter)),
                Column('features', ARRAY(String)),
                Column('splash', String, nullable=True))
        self.tb_channels = Table('channels', meta,
                Column('channel_id', BigInteger, primary_key=True),
                Column('name', String),
                Column('is_nsfw', Boolean),
                Column('is_deleted', Boolean),
                Column('position', SmallInteger),
                Column('topic', UnicodeText, nullable=True),
                Column('changed_roles', ARRAY(BigInteger)),
                Column('category_id', BigInteger,
                    ForeignKey('channel_categories.category_id'), nullable=True),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')))
        self.tb_voice_channels = Table('voice_channels', meta,
                Column('voice_channel_id', BigInteger, primary_key=True),
                Column('name', Unicode),
                Column('is_deleted', Boolean),
                Column('position', SmallInteger),
                Column('bitrate', Integer),
                Column('user_limit', SmallInteger),
                Column('changed_roles', ARRAY(BigInteger)),
                Column('category_id', BigInteger,
                    ForeignKey('channel_categories.category_id'), nullable=True),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')))
        self.tb_channel_categories = Table('channel_categories', meta,
                Column('category_id', BigInteger, primary_key=True),
                Column('name', Unicode),
                Column('position', SmallInteger),
                Column('is_deleted', Boolean),
                Column('is_nsfw', Boolean),
                Column('changed_roles', ARRAY(BigInteger)),
                Column('parent_category_id', BigInteger,
                    ForeignKey('channel_categories.category_id'), nullable=True),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')))
        self.tb_users = Table('users', meta,
                Column('user_id', BigInteger, primary_key=True),
                Column('name', Unicode),
                Column('discriminator', SmallInteger),
                Column('avatar', String, nullable=True),
                Column('is_deleted', Boolean),
                Column('is_bot', Boolean))
        self.tb_guild_membership = Table('guild_membership', meta,
                Column('user_id', BigInteger,
                    ForeignKey('users.user_id'), primary_key=True),
                Column('guild_id', BigInteger,
                    ForeignKey('guilds.guild_id'), primary_key=True),
                Column('is_member', Boolean),
                Column('joined_at', DateTime, nullable=True),
                Column('nick', Unicode(32), nullable=True),
                UniqueConstraint('user_id', 'guild_id', name='uq_guild_membership'))
        self.tb_role_membership = Table('role_membership', meta,
                Column('role_id', BigInteger, ForeignKey('roles.role_id')),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')),
                Column('user_id', BigInteger, ForeignKey('users.user_id')),
                UniqueConstraint('role_id', 'user_id', name='uq_role_membership'))
        self.tb_emojis = Table('emojis', meta,
                Column('emoji_id', BigInteger),
                Column('emoji_unicode', Unicode(7)),
                Column('is_custom', Boolean),
                Column('is_managed', Boolean, nullable=True),
                Column('is_deleted', Boolean),
                Column('name', ARRAY(String)),
                Column('category', ARRAY(String)),
                Column('roles', ARRAY(BigInteger), nullable=True),
                Column('guild_id', BigInteger, nullable=True),
                UniqueConstraint('emoji_id', 'emoji_unicode', name='uq_emoji'))
        self.tb_roles = Table('roles', meta,
                Column('role_id', BigInteger, primary_key=True),
                Column('name', Unicode),
                Column('color', Integer),
                Column('raw_permissions', BigInteger),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')),
                Column('is_hoisted', Boolean),
                Column('is_managed', Boolean),
                Column('is_mentionable', Boolean),
                Column('is_deleted', Boolean),
                Column('position', SmallInteger))
        self.tb_audit_log = Table('audit_log', meta,
                Column('audit_entry_id', BigInteger, primary_key=True),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')),
                Column('action', Enum(discord.AuditLogAction)),
                Column('user_id', BigInteger, ForeignKey('users.user_id')),
                Column('reason', Unicode, nullable=True),
                Column('category', Enum(discord.AuditLogActionCategory), nullable=True),
                Column('before', JSON),
                Column('after', JSON),
                UniqueConstraint('audit_entry_id', 'guild_id', name='uq_audit_log'))
        self.tb_channel_crawl = Table('channel_crawl', meta,
                Column('channel_id', BigInteger,
                    ForeignKey('channels.channel_id'), primary_key=True),
                Column('last_message_id', BigInteger))
        self.tb_audit_log_crawl = Table('audit_log_crawl', meta,
                Column('guild_id', BigInteger,
                    ForeignKey('guilds.guild_id'), primary_key=True),
                Column('last_audit_entry_id', BigInteger))

        # Caches
        self.message_cache = LruCache(cache_size['event-size'])
        self.typing_cache = LruCache(cache_size['event-size'])
        self.status_cache = LruCache(cache_size['event-size'])
        self.activity_cache = LruCache(cache_size['event-size'])
        self.guild_cache = LruCache(cache_size['lookup-size'])
        self.channel_cache = LruCache(cache_size['lookup-size'])
        self.voice_channel_cache = LruCache(cache_size['lookup-size'])
        self.channel_category_cache = LruCache(cache_size['lookup-size'])
        self.user_cache = LruCache(cache_size['lookup-size'])
        self.emoji_cache = LruCache(cache_size['lookup-size'])
        self.role_cache = LruCache(cache_size['lookup-size'])

        # Create tables
        meta.create_all(self.db)
        self.logger.info("Created all tables.")

    # Transaction logic
    def transaction(self):
        return _Transaction(self.conn, self.logger)

    # Guild
    def upsert_guild(self, trans, guild):
        values = guild_values(guild)
        if self.guild_cache.get(guild.id) == values:
            self.logger.debug(f"Guild lookup for {guild.id} is already up-to-date")
            return

        self.logger.info(f"Updating lookup data for guild {guild.name}")
        ups = p_insert(self.tb_guilds) \
                .values(values) \
                .on_conflict_do_update(
                        index_elements=['guild_id'],
                        index_where=(self.tb_guilds.c.guild_id == guild.id),
                        set_=values,
                )
        trans.conn.execute(ups)
        self.guild_cache[guild.id] = values

    # Messages
    def add_message(self, trans, message):
        values = message_values(message)

        if self.message_cache.get(message.id) == values:
            self.logger.debug(f"Message lookup for {message.id} is already up-to-date")
            return

        self.logger.info(f"Inserting message {message.id}")
        ins = self.tb_messages \
                .insert() \
                .values(values)
        trans.execute(ins)
        self.message_cache[message.id] = values

        self.upsert_user(trans, message.author)
        self.insert_mentions(trans, message)

    def edit_message(self, trans, before, after):
        self.logger.info(f"Updating message {after.id}")
        upd = self.tb_messages \
                .update() \
                .values({
                    'edited_at': after.edited_at,
                    'content': after.content,
                    'embeds': [embed.to_dict() for embed in after.embeds],
                }) \
                .where(self.tb_messages.c.message_id == after.id)
        trans.execute(upd)

        self.insert_mentions(trans, after)

    def remove_message(self, trans, message):
        self.logger.info(f"Deleting message {message.id}")
        upd = self.tb_messages \
                .update() \
                .values(deleted_at=datetime.now()) \
                .where(self.tb_messages.c.message_id == message.id)
        trans.execute(upd)
        self.message_cache.pop(message.id, None)

    def insert_message(self, trans, message):
        values = message_values(message)
        if self.message_cache.get(message.id) == values:
            self.logger.debug(f"Message lookup for {message.id} is already up-to-date")
            return

        self.logger.debug(f"Inserting message {message.id}")
        ins = p_insert(self.tb_messages) \
                .values(values) \
                .on_conflict_do_nothing(index_elements=['message_id'])
        trans.execute(ins)
        self.message_cache[message.id] = values

        self.upsert_user(trans, message.author)
        self.insert_mentions(trans, message)

    # Mentions
    def insert_mentions(self, trans, message):
        self.logger.debug(f"Inserting all mentions in message {message.id}")

        for id in message.raw_mentions:
            if id > MAX_ID:
                self.logger.error(f"User mention was too long: {id}")
                continue

            self.logger.debug(f"User mention: {id}")
            ins = p_insert(self.tb_mentions) \
                    .values({
                        'mentioned_id': id,
                        'type': MentionType.USER,
                        'message_id': message.id,
                        'channel_id': message.channel.id,
                        'guild_id': message.guild.id,
                    }) \
                    .on_conflict_do_nothing(index_elements=['mentioned_id', 'type', 'message_id'])
            trans.execute(ins)

        for id in message.raw_role_mentions:
            if id > MAX_ID:
                self.logger.error(f"Role mention was too long: {id}")
                continue

            self.logger.debug(f"Role mention: {id}")
            ins = p_insert(self.tb_mentions) \
                    .values({
                        'mentioned_id': id,
                        'type': MentionType.ROLE,
                        'message_id': message.id,
                        'channel_id': message.channel.id,
                        'guild_id': message.guild.id,
                    }) \
                    .on_conflict_do_nothing(index_elements=['mentioned_id', 'type', 'message_id'])
            trans.execute(ins)

        for id in message.raw_channel_mentions:
            if id > MAX_ID:
                self.logger.error(f"Channel mention was too long: {id}")
                continue

            self.logger.debug(f"Channel mention: {id}")
            ins = p_insert(self.tb_mentions) \
                    .values({
                        'mentioned_id': id,
                        'type': MentionType.CHANNEL,
                        'message_id': message.id,
                        'channel_id': message.channel.id,
                        'guild_id': message.guild.id,
                    }) \
                    .on_conflict_do_nothing(index_elements=['mentioned_id', 'type', 'message_id'])
            trans.execute(ins)

    # Typing
    def typing(self, trans, channel, user, when):
        key = (when, user.id, channel.id)
        if self.typing_cache.get(key, False):
            self.logger.debug("Typing lookup is up-to-date")
            return

        self.logger.info(f"Inserting typing event for user {user.id}")
        ins = self.tb_typing \
                .insert() \
                .values({
                    'timestamp': when,
                    'user_id': user.id,
                    'channel_id': channel.id,
                    'guild_id': channel.guild.id,
                })
        trans.execute(ins)
        self.typing_cache[key] = True

    # Status
    def status_change(self, trans, member):
        timestamp = datetime.now()
        key = (timestamp, member.id)

        if self.status_cache.get(key, None):
            self.logger.debug("Status change lookup is up-to-date")
            return

        self.logger.info(f"Inserting status change event for user {member.id}")
        ins = self.tb_status \
                .insert() \
                .values({
                    'timestamp': timestamp,
                    'user_id': member.id,
                    'status': member.status,
                })
        trans.execute(ins)
        self.status_cache[key] = member.status

    # Activity
    def activity_change(self, trans, member):
        timestamp = datetime.now()
        key = (timestamp, member.id)

        if self.activity_cache.get(key, None):
            self.logger.debug("Activity change lookup is up-to-date")
            return

        self.logger.info(f"Inserting activity change event for user {member.id}")
        values = activity_values(member)
        ins = self.tb_activities \
                .insert() \
                .values(values)
        trans.execute(ins)
        self.activity_cache[key] = values

=======
>>>>>>> Hook in events for status and game changes.
    # Reactions
    def add_reaction(self, trans, reaction, user):
        self.logger.info(f"Inserting live reaction for user {user.id} on message {reaction.message.id}")
        self.upsert_emoji(trans, reaction.emoji)
        self.upsert_user(trans, user)
        values = reaction_values(reaction, user, True)
        ins = self.tb_reactions \
                .insert() \
                .values(values)
        trans.execute(ins)

    def remove_reaction(self, trans, reaction, user):
        self.logger.info(f"Deleting reaction for user {user.id} on message {reaction.message.id}")
        data = EmojiData(reaction.emoji)
        upd = self.tb_reactions \
                .update() \
                .values(deleted_at=datetime.now()) \
                .where(self.tb_reactions.c.message_id == reaction.message.id) \
                .where(self.tb_reactions.c.emoji_id == data.id) \
                .where(self.tb_reactions.c.emoji_unicode == data.unicode) \
                .where(self.tb_reactions.c.user_id == user.id)
        trans.execute(upd)

    def insert_reaction(self, trans, reaction, users):
        self.logger.info(f"Inserting past reactions for {reaction.message.id}")
        self.upsert_emoji(trans, reaction.emoji)
        data = EmojiData(reaction.emoji)
        for user in users:
            self.upsert_user(trans, user)
            values = reaction_values(reaction, user, False)
            self.logger.debug(f"Inserting single reaction {data} from {user.id}")
            ins = p_insert(self.tb_reactions) \
                    .values(values) \
                    .on_conflict_do_nothing(constraint='uq_reactions')
            trans.execute(ins)

    def clear_reactions(self, trans, message):
        self.logger.info(f"Deleting all reactions on message {message.id}")
        upd = self.tb_reactions \
                .update() \
                .values(deleted_at=datetime.now()) \
                .where(self.tb_reactions.c.message_id == message.id)
        trans.execute(upd)

    # Pins (TODO)
    def add_pin(self, trans, announce, message):
        # pylint: disable=unreachable
        raise NotImplementedError

        self.logger.info(f"Inserting pin for message {message.id}")
        ins = self.tb_pins \
                .insert() \
                .values({
                    'pin_id': announce.id,
                    'message_id': message.id,
                    'pinner_id': announce.author.id,
                    'user_id': message.author.id,
                    'channel_id': message.channel.id,
                    'guild_id': message.guild.id,
                })
        trans.execute(ins)

    def remove_pin(self, trans, announce, message):
        # pylint: disable=unreachable
        raise NotImplementedError

        self.logger.info(f"Deleting pin for message {message.id}")
        delet = self.tb_pins \
                .delete() \
                .where(self.tb_pins.c.pin_id == announce.id) \
                .where(self.tb_pins.c.message_id == message.id)
        trans.execute(delet)

    # Roles
    def add_role(self, trans, role):
        if role.id in self.role_cache:
            self.logger.debug(f"Role {role.id} already inserted.")
            return

        self.logger.info(f"Inserting role {role.id}")
        values = role_values(role)
        ins = self.tb_roles \
                .insert() \
                .values(values)
        trans.execute(ins)
        self.role_cache[role.id] = values

    def _update_role(self, trans, role):
        self.logger.info(f"Updating role {role.id} in guild {role.guild.id}")
        values = role_values(role)
        upd = self.tb_roles \
                .update() \
                .where(self.tb_roles.c.role_id == role.id) \
                .values(values)
        trans.execute(upd)
        self.role_cache[role.id] = values

    def update_role(self, trans, role):
        if role.id in self.role_cache:
            self._update_role(trans, role)
        else:
            self.upsert_role(trans, role)

    def remove_role(self, trans, role):
        self.logger.info(f"Deleting role {role.id}")
        upd = self.tb_roles \
                .update() \
                .values(is_deleted=True) \
                .where(self.tb_roles.c.role_id == role.id)
        trans.execute(upd)
        self.role_cache.pop(role.id, None)

    def upsert_role(self, trans, role):
        values = role_values(role)
        if self.role_cache.get(role.id) == values:
            self.logger.debug(f"Role lookup for {role.id} is already up-to-date")
            return

        self.logger.debug(f"Updating lookup data for role {role.name}")
        ups = p_insert(self.tb_roles) \
                .values(values) \
                .on_conflict_do_update(
                        index_elements=['role_id'],
                        index_where=(self.tb_roles.c.role_id == role.id),
                        set_=values,
                )
        trans.execute(ups)
        self.role_cache[role.id] = values

    # Channels
    def add_channel(self, trans, channel):
        if channel.id in self.channel_cache:
            self.logger.debug(f"Channel {channel.id} already inserted.")
            return

        self.logger.info(f"Inserting new channel {channel.id} for guild {channel.guild.id}")
        values = channel_values(channel)
        ins = self.tb_channels \
                .insert() \
                .values(values)
        trans.execute(ins)
        self.channel_cache[channel.id] = values

    def _update_channel(self, trans, channel):
        self.logger.info(f"Updating channel {channel.id} in guild {channel.guild.id}")
        values = channel_values(channel)
        upd = self.tb_channels \
                .update() \
                .where(self.tb_channels.c.channel_id == channel.id) \
                .values(values)
        trans.execute(upd)
        self.channel_cache[channel.id] = values

    def update_channel(self, trans, channel):
        if channel.id in self.channel_cache:
            self._update_channel(trans, channel)
        else:
            self.upsert_channel(trans, channel)

    def remove_channel(self, trans, channel):
        self.logger.info(f"Deleting channel {channel.id} in guild {channel.guild.id}")
        upd = self.tb_channels \
                .update() \
                .values(is_deleted=True) \
                .where(self.tb_channels.c.channel_id == channel.id)
        trans.execute(upd)
        self.channel_cache.pop(channel.id, None)

    def upsert_channel(self, trans, channel):
        values = channel_values(channel)
        if self.channel_cache.get(channel.id) == values:
            self.logger.debug(f"Channel lookup for {channel.id} is already up-to-date")
            return

        self.logger.debug(f"Updating lookup data for channel #{channel.name}")
        ups = p_insert(self.tb_channels) \
                .values(values) \
                .on_conflict_do_update(
                        index_elements=['channel_id'],
                        index_where=(self.tb_channels.c.channel_id == channel.id),
                        set_=values,
                )
        trans.execute(ups)
        self.channel_cache[channel.id] = values

    # Voice Channels
    def add_voice_channel(self, trans, channel):
        if channel in self.voice_channel_cache:
            self.logger.debug(f"Voice channel {channel.id} already inserted")
            return

        self.logger.info("Inserting new voice channel {channel.id} for guild {channel.guild.id}")
        values = voice_channel_values(channel)
        ins = self.tb_voice_channels \
                .insert() \
                .values(values)
        trans.execute(ins)
        self.voice_channel_cache[channel.id] = values

    def _update_voice_channel(self, trans, channel):
        self.logger.info(f"Updating voice channel {channel.id} in guild {channel.guild.id}")
        values = voice_channel_values(channel)
        upd = self.tb_voice_channels \
                .update() \
                .where(self.tb_voice_channels.c.voice_channel_id == channel.id) \
                .values(values)
        trans.execute(upd)
        self.voice_channel_cache[channel.id] = values

    def update_voice_channel(self, trans, channel):
        if channel.id in self.voice_channel_cache:
            self._update_voice_channel(trans, channel)
        else:
            self.upsert_channel(trans, channel)

    def remove_voice_channel(self, trans, channel):
        self.logger.info(f"Deleting voice channel {channel.id} in guild {channel.guild.id}")
        upd = self.tb_voice_channels \
                .update() \
                .values(is_deleted=True) \
                .where(self.tb_voice_channels.c.voice_channel_id == channel.id)
        trans.execute(upd)
        self.voice_channel_cache.pop(channel.id, None)

    def upsert_voice_channel(self, trans, channel):
        values = voice_channel_values(channel)
        if self.voice_channel_cache.get(channel.id) == values:
            self.logger.debug(f"Voice channel lookup for {channel.id} is already up-to-date")
            return

        self.logger.debug(f"Updating lookup data for voice channel '{channel.name}'")
        ups = p_insert(self.tb_voice_channels) \
                .values(values) \
                .on_conflict_do_update(
                        index_elements=['voice_channel_id'],
                        index_where=(self.tb_voice_channels.c.voice_channel_id == channel.id),
                        set_=values,
                )
        trans.execute(ups)
        self.voice_channel_cache[channel.id] = values

    # Channel Categories
    def add_channel_category(self, trans, category):
        if category.id in self.channel_category_cache:
            self.logger.debug(f"Channel category {category.id} already inserted.")
            return

        self.logger.info(f"Inserting new category {category.id} for guild {category.guild.id}")
        values = channel_categories_values(category)
        ins = self.tb_channel_categories \
                .insert() \
                .values(values)
        trans.execute(ins)
        self.channel_category_cache[category.id] = values

    def _update_channel_category(self, trans, category):
        self.logger.info(f"Updating channel category {category.id} in guild {category.guild.id}")
        values = channel_categories_values(category)
        upd = self.tb_channel_categories \
                .update() \
                .where(self.tb_channel_categories.c.category_id == category.id) \
                .values(values)
        trans.execute(upd)
        self.channel_category_cache[category.id] = values

    def update_channel_category(self, trans, category):
        if category.id in self.channel_category_cache:
            self._update_channel_category(trans, category)
        else:
            self.upsert_channel_category(trans, category)

    def remove_channel_category(self, trans, category):
        self.logger.info(f"Deleting channel category {category.id} in guild {category.guild.id}")
        upd = self.tb_channel_categories \
                .update() \
                .values(is_deleted=True) \
                .where(self.tb_channels.c.category_id == category.id)
        trans.execute(upd)
        self.channel_category_cache.pop(category.id, None)

    def upsert_channel_category(self, trans, category):
        values = channel_categories_values(category)
        if self.channel_cache.get(category.id) == values:
            self.logger.debug(f"Channel category lookup for {category.id} is already up-to-date")
            return

        self.logger.debug(f"Updating lookup data for channel category {category.name}")
        ups = p_insert(self.tb_channel_categories) \
                .values(values) \
                .on_conflict_do_update(
                        index_elements=['category_id'],
                        index_where=(self.tb_channel_categories.c.category_id == category.id),
                        set_=values,
                )
        trans.execute(ups)
        self.channel_category_cache[category.id] = values

    # Users
    def add_user(self, trans, user):
        if user.id in self.user_cache:
            self.logger.debug(f"User {user.id} already inserted.")
            return

        self.logger.info(f"Inserting user {user.id}")
        values = user_values(user)
        ins = self.tb_users \
                .insert() \
                .values(values)
        trans.execute(ins)
        self.user_cache[user.id] = values

    def _update_user(self, trans, user):
        self.logger.info(f"Updating user {user.id}")
        values = user_values(user)
        upd = self.tb_users \
                .update() \
                .where(self.tb_users.c.user_id == user.id) \
                .values(values)
        trans.execute(upd)
        self.user_cache[user.id] = values

    def update_user(self, trans, user):
        if user.id in self.user_cache:
            self._update_user(trans, user)
        else:
            self.upsert_user(trans, user)

    def remove_user(self, trans, user):
        self.logger.info(f"Removing user {user.id}")
        upd = self.tb_users \
                .update() \
                .values(is_deleted=True) \
                .where(self.tb_users.c.user_id == user.id)
        trans.execute(upd)
        self.user_cache.pop(user.id, None)

    def upsert_user(self, trans, user):
        self.logger.debug(f"Upserting user {user.id}")
        values = user_values(user)
        if self.user_cache.get(user.id) == values:
            self.logger.debug(f"User lookup for {user.id} is already up-to-date")
            return

        ups = p_insert(self.tb_users) \
                .values(values) \
                .on_conflict_do_update(
                        index_elements=['user_id'],
                        index_where=(self.tb_users.c.user_id == user.id),
                        set_=values,
                )
        trans.execute(ups)
        self.user_cache[user.id] = values

    # Members
    def update_member(self, trans, member):
        self.logger.info(f"Updating member data for {member.id}")
        upd = self.tb_guild_membership \
                .update() \
                .where(and_(
                    self.tb_guild_membership.c.user_id == member.id,
                    self.tb_guild_membership.c.guild_id == member.guild.id,
                )) \
                .values(nick=member.nick)
        trans.execute(upd)

        self._delete_role_membership(trans, member)
        self._insert_role_membership(trans, member)

    def _delete_role_membership(self, trans, member):
        delet = self.tb_role_membership \
                .delete() \
                .where(and_(
                    self.tb_role_membership.c.user_id == member.id,
                    self.tb_role_membership.c.guild_id == member.guild.id,
                    self.tb_role_membership.c.role_id not in member.roles,
                ))
        trans.execute(delet)

    def _insert_role_membership(self, trans, member):
        for role in member.roles:
            values = role_member_values(member, role)
            ins = self.tb_role_membership \
                    .insert() \
                    .values(values)
            trans.execute(ins)

    def remove_member(self, trans, user_id, guild_id):
        self.logger.debug(f"Removing member {user_id} from guild {guild_id}")
        upd = self.tb_guild_membership \
                .update() \
                .where(and_(
                    self.tb_guild_membership.c.user_id == user_id,
                    self.tb_guild_membership.c.guild_id == guild_id,
                )) \
                .values(is_member=False)
        trans.execute(upd)

        # Don't delete role membership

    def remove_old_members(self, trans, guild):
        # Since pylint complains about <thing> == True.
        # We need to do this otherwise silly comparison
        # because it's not a comparison at all, it's actually
        # creating a SQLAlchemy "equality" object that is used
        # to generate the query.
        #
        # pylint: disable=singleton-comparison

        self.logger.info(f"Deleting old members from guild {guild.name}")
        sel = select([self.tb_guild_membership]) \
                .where(and_(
                    self.tb_guild_membership.c.guild_id == guild.id,
                    self.tb_guild_membership.c.is_member == True,
                ))
        result = trans.execute(sel)

        for row in result.fetchall():
            user_id = row[0]
            member = guild.get_member(user_id)
            if member is None:
                self.remove_member(trans, user_id, guild.id)

    def upsert_member(self, trans, member):
        self.logger.debug(f"Upserting member data for {member.id}")
        values = guild_member_values(member)
        ups = p_insert(self.tb_guild_membership) \
                .values(values) \
                .on_conflict_do_update(
                        constraint='uq_guild_membership',
                        set_=values,
                )
        trans.execute(ups)

        self._delete_role_membership(trans, member)
        self._insert_role_membership(trans, member)

    # Emojis
    def add_emoji(self, trans, emoji):
        data = EmojiData(emoji)
        if data.cache_id in self.emoji_cache:
            self.logger.debug(f"Emoji {data} already inserted.")
            return

        self.logger.info(f"Inserting emoji {data}")
        values = emoji.values()
        ins = self.tb_emojis \
                .insert() \
                .values(values)
        trans.execute(ins)
        self.emoji_cache[data.cache_id] = values

    def remove_emoji(self, trans, emoji):
        data = EmojiData(emoji)
        self.logger.info(f"Deleting emoji {data}")

        upd = self.tb_emojis \
                .update() \
                .values(is_deleted=True) \
                .where(self.tb_emojis.c.emoji_id == data.id) \
                .where(self.tb_emojis.c.emoji_unicode == data.unicode)
        trans.execute(upd)
        self.emoji_cache.pop(data.cache_id, None)

    def upsert_emoji(self, trans, emoji):
        data = EmojiData(emoji)
        values = data.values()
        if self.emoji_cache.get(data.cache_id) == values:
            self.logger.debug(f"Emoji lookup for {data} is already up-to-date")
            return

        self.logger.debug(f"Upserting emoji {data}")
        ups = p_insert(self.tb_emojis) \
                .values(values) \
                .on_conflict_do_update(
                    index_elements=['emoji_id', 'emoji_unicode'],
                    index_where=and_(
                        self.tb_emojis.c.emoji_id == data.id,
                        self.tb_emojis.c.emoji_unicode == data.unicode,
                    ),
                    set_=values,
                )
        trans.execute(ups)
        self.emoji_cache[data.cache_id] = values

    # Audit log
    def insert_audit_log_entry(self, trans, guild, entry):
        self.logger.debug(f"Inserting audit log entry {entry.id} from {guild.name}")
        data = AuditLogData(entry, guild)
        values = data.values()
        ins = p_insert(self.tb_audit_log) \
                .values(values) \
                .on_conflict_do_nothing(index_elements=['audit_entry_id'])
        trans.execute(ins)

    # Crawling history
    def lookup_channel_crawl(self, trans, channel):
        self.logger.info(f"Looking up channel crawl progress for {channel.guild.name} #{channel.name}")
        sel = select([self.tb_channel_crawl]) \
                .where(self.tb_channel_crawl.c.channel_id == channel.id)
        result = trans.execute(sel)

        if result.rowcount:
            _, last_id = result.fetchone()
            return last_id
        else:
            return None

    def insert_channel_crawl(self, trans, channel, last_id):
        self.logger.info(f"Inserting new channel crawl progress for {channel.guild.name} #{channel.name}")

        ins = self.tb_channel_crawl \
                .insert() \
                .values({
                    'channel_id': channel.id,
                    'last_message_id': last_id,
                })
        trans.execute(ins)

    def update_channel_crawl(self, trans, channel, last_id):
        self.logger.info(f"Updating channel crawl progress for {channel.guild.name} #{channel.name}: {last_id}")

        upd = self.tb_channel_crawl \
                .update() \
                .values(last_message_id=last_id) \
                .where(self.tb_channel_crawl.c.channel_id == channel.id)
        trans.execute(upd)

    def delete_channel_crawl(self, trans, channel):
        self.logger.info(f"Deleting channel crawl progress for {channel.guild.name} #{channel.name}")

        delet = self.tb_channel_crawl \
                .delete() \
                .where(self.tb_channel_crawl.c.channel_id == channel.id)
        trans.execute(delet)

    def lookup_audit_log_crawl(self, trans, guild):
        self.logger.info(f"Looking for audit log crawl progress for {guild.name}")
        sel = select([self.tb_audit_log_crawl]) \
                .where(self.tb_audit_log_crawl.c.guild_id == guild.id)
        result = trans.execute(sel)

        if result.rowcount:
            _, last_id = result.fetchone()
            return last_id
        else:
            return None

    def insert_audit_log_crawl(self, trans, guild, last_id):
        self.logger.info(f"Inserting new audit log crawl progress for {guild.name}")

        ins = self.tb_audit_log_crawl \
                .insert() \
                .values({
                    'guild_id': guild.id,
                    'last_audit_entry_id': last_id,
                })
        trans.execute(ins)

    def update_audit_log_crawl(self, trans, guild, last_id):
        self.logger.info(f"Updating audit log crawl progress for {guild.name}")

        upd = self.tb_audit_log_crawl \
                .update() \
                .values(last_audit_entry_id=last_id) \
                .where(self.tb_audit_log_crawl.c.guild_id == guild.id)
        trans.execute(upd)

    def delete_audit_log_crawl(self, trans, guild):
        self.logger.info(f"Delete audit log crawl progress for {guild.name}")

        delet = self.tb_audit_log_crawl \
                .delete() \
                .where(self.tb_audit_log_crawl.c.guild_id == guild.id)
        trans.execute(delet)
