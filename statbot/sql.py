#
# sql.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import functools
import unicodedata

import discord
from sqlalchemy import ARRAY, Boolean, BigInteger, Column, DateTime, Enum
from sqlalchemy import Integer, String, Table, Unicode, UnicodeText
from sqlalchemy import ForeignKey, MetaData, create_engine, and_
from sqlalchemy.dialects.postgresql import insert as p_insert

from .orm import ORMHandler
from .util import embeds_to_json, get_emoji_id, get_null_id, null_logger

Column = functools.partial(Column, nullable=False)

__all__ = [
    'DiscordSqlHandler',
]

class _Transaction:
    __slots__ = (
        'sql',
        'logger',
        'conn',
        'trans',
        'ok',
    )

    def __init__(self, sql):
        self.sql = sql
        self.logger = sql.logger
        self.conn = sql.db.connect()
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
            self.logger.error("Exception occurred in 'with' scope!")
            self.logger.debug("Rolling back transaction...")
            self.ok = False
            self.trans.rollback()

    def execute(self, *args, **kwargs):
        self.conn.execute(*args, **kwargs)

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
        'meta',
        'logger',
        'orm',

        'tb_messages',
        'tb_reactions',
        'tb_typing',
        'tb_pins',
        'tb_guilds',
        'tb_voice_channels',
        'tb_channels',
        'tb_users',
        'tb_nicknames',
        'tb_emojis',
        'tb_roles',

        'tb_channel_hist',
        'tb_ranges_orm',
        'tb_audit_hist',

        'guild_cache',
        'channel_cache',
        'voice_channel_cache',
        'user_cache',
        'emoji_cache',
        'role_cache',
    )

    def __init__(self, addr, logger=null_logger):
        logger.info(f"Opening database: '{addr}'")
        self.db = create_engine(addr)
        self.meta = MetaData(self.db)
        self.logger = logger

        # Primary tables
        self.tb_messages = Table('messages', self.meta,
                Column('message_id', BigInteger, primary_key=True),
                Column('created_at', DateTime),
                Column('edited_at', DateTime, nullable=True),
                Column('is_edited', Boolean),
                Column('is_deleted', Boolean),
                Column('message_type', Enum(discord.MessageType)),
                Column('system_content', UnicodeText),
                Column('content', UnicodeText),
                Column('embeds', UnicodeText),
                Column('attachments', Integer),
                Column('user_id', BigInteger, ForeignKey('users.user_id')),
                Column('channel_id', BigInteger, ForeignKey('channels.channel_id')),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')))
        self.tb_reactions = Table('reactions', self.meta,
                Column('message_id', BigInteger, ForeignKey('messages.message_id')),
                Column('emoji_id', BigInteger, ForeignKey('emojis.emoji_id')),
                Column('user_id', BigInteger, ForeignKey('users.user_id')),
                Column('channel_id', BigInteger, ForeignKey('channels.channel_id')),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')))
        self.tb_typing = Table('typing', self.meta,
                Column('timestamp', DateTime),
                Column('user_id', BigInteger, ForeignKey('users.user_id')),
                Column('channel_id', BigInteger, ForeignKey('channels.user_id')),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')))
        self.tb_pins = Table('pins', self.meta,
                Column('pin_id', BigInteger, primary_key=True),
                Column('message_id', BigInteger,
                    ForeignKey('messages.message_id'), primary_key=True),
                Column('pinner_id', BigInteger, ForeignKey('users.user_id')),
                Column('user_id', BigInteger, ForeignKey('users.user_id')),
                Column('channel_id', BigInteger, ForeignKey('channels.channel_id')),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')))

        # Lookup tables
        self.tb_guilds = Table('guilds', self.meta,
                Column('guild_id', BigInteger, primary_key=True),
                Column('owner_id', BigInteger, ForeignKey('users.user_id')),
                Column('name', Unicode),
                Column('icon', String),
                Column('region', Enum(discord.VoiceRegion)),
                Column('afk_channel_id', BigInteger, nullable=True),
                Column('afk_timeout', Integer),
                Column('mfa', Boolean),
                Column('verification_level', Enum(discord.VerificationLevel)),
                Column('explicit_content_filter', Enum(discord.ContentFilter)),
                Column('features', ARRAY(String)),
                Column('splash', String, nullable=True))
        self.tb_voice_channels = Table('voice_channels', self.meta,
                Column('voice_channel_id', BigInteger, primary_key=True),
                Column('name', Unicode),
                Column('is_default', Boolean),
                Column('is_deleted', Boolean),
                Column('position', Integer),
                Column('bitrate', Integer),
                Column('user_limit', Integer),
                Column('changed_roles', ARRAY(BigInteger)),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')))
        self.tb_channels = Table('channels', self.meta,
                Column('channel_id', BigInteger, primary_key=True),
                Column('name', String),
                Column('is_default', Boolean),
                Column('is_nsfw', Boolean),
                Column('is_deleted', Boolean),
                Column('position', Integer),
                Column('topic', UnicodeText, nullable=True),
                Column('changed_roles', ARRAY(BigInteger)),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')))
        self.tb_users = Table('users', self.meta,
                Column('user_id', BigInteger, primary_key=True),
                Column('name', Unicode),
                Column('discriminator', Integer),
                Column('is_deleted', Boolean),
                Column('is_bot', Boolean))
        self.tb_nicknames = Table('nicknames', self.meta,
                Column('user_id', BigInteger,
                    ForeignKey('users.user_id'), primary_key=True),
                Column('guild_id', BigInteger,
                    ForeignKey('guilds.guild_id'), primary_key=True),
                Column('nickname', Unicode(32), nullable=True))
        self.tb_emojis = Table('emojis', self.meta,
                Column('emoji_id', BigInteger, primary_key=True),
                Column('name', String),
                Column('is_deleted', Boolean),
                Column('category', String),
                Column('unicode', Unicode(1), nullable=True),
                Column('guild_id', BigInteger,
                    ForeignKey('guilds.guild_id'), nullable=True))
        self.tb_roles = Table('roles', self.meta,
                Column('role_id', BigInteger, primary_key=True),
                Column('name', Unicode),
                Column('color', Integer),
                Column('raw_permissions', BigInteger),
                Column('guild_id', BigInteger, ForeignKey('guilds.guild_id')),
                Column('is_hoisted', Boolean),
                Column('is_managed', Boolean),
                Column('is_mentionable', Boolean),
                Column('is_deleted', Boolean),
                Column('position', Integer))

        # History tables
        self.orm = ORMHandler(self.db, self.meta, self.logger)
        self.tb_channel_hist = self.orm.tb_channel_hist
        self.tb_ranges_orm = self.orm.tb_ranges_orm

        # Lookup caches
        self.guild_cache = {}
        self.channel_cache = {}
        self.voice_channel_cache = {}
        self.user_cache = {}
        self.emoji_cache = {}
        self.role_cache = {}

        # Create tables
        self.meta.create_all(self.db)
        self.logger.info("Created all tables.")

    # Transaction logic
    def transaction(self):
        return _Transaction(self)

    # Value builders
    @staticmethod
    def _guild_values(guild):
        return {
            'guild_id': guild.id,
            'owner_id': guild.owner.id,
            'name': guild.name,
            'icon': guild.icon,
            'region': guild.region,
            'afk_channel_id': get_null_id(guild.afk_channel),
            'afk_timeout': guild.afk_timeout,
            'mfa': bool(guild.mfa_level),
            'verification_level': guild.verification_level,
            'explicit_content_filter': guild.explicit_content_filter,
            'features': guild.features,
            'splash': guild.splash,
        }

    @staticmethod
    def _message_values(message):
        if message.type == discord.MessageType.default:
            system_content = '';
        else:
            system_content = message.system_content

        return {
            'message_id': message.id,
            'created_at': message.created_at,
            'edited_at': message.edited_at,
            'is_edited': message.edited_at is not None,
            'is_deleted': False,
            'message_type': message.type,
            'system_content': system_content,
            'content': message.content,
            'embeds': embeds_to_json(message.embeds),
            'attachments': len(message.attachments),
            'user_id': message.author.id,
            'channel_id': message.channel.id,
            'guild_id': message.guild.id,
        }

    @staticmethod
    def _channel_values(channel):
        return {
            'channel_id': channel.id,
            'name': channel.name,
            'is_default': channel.is_default(),
            'is_nsfw': channel.is_nsfw(),
            'is_deleted': False,
            'position': channel.position,
            'topic': channel.topic,
            'changed_roles': [role.id for role in channel.changed_roles],
            'guild_id': channel.guild.id,
        }

    @staticmethod
    def _voice_channel_values(channel):
        return {
            'voice_channel_id': channel.id,
            'name': channel.name,
            'is_default': channel.is_default(),
            'is_deleted': False,
            'position': channel.position,
            'bitrate': channel.bitrate,
            'user_limit': channel.user_limit,
            'changed_roles': [role.id for role in channel.changed_roles],
            'guild_id': channel.guild.id,
        }

    @staticmethod
    def _user_values(user):
        return {
            'user_id': user.id,
            'name': user.name,
            'discriminator': user.discriminator,
            'is_deleted': False,
            'is_bot': user.bot,
        }

    @staticmethod
    def _nick_values(member):
        return {
            'user_id': member.id,
            'guild_id': member.guild.id,
            'nickname': member.nick,
        }

    @staticmethod
    def _emoji_values(emoji):
        if isinstance(emoji, str):
            return {
                'emoji_id': ord(emoji),
                'name': unicodedata.name(emoji),
                'is_deleted': False,
                'category': unicodedata.category(emoji),
                'unicode': emoji,
                'guild_id': None,
            }
        else:
            return {
                'emoji_id': emoji.id,
                'name': emoji.name,
                'is_deleted': False,
                'category': f'(custom:{emoji.guild.name})',
                'unicode': None,
                'guild_id': emoji.guild.id,
            }

    @staticmethod
    def _role_values(role):
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

    # Guild
    def upsert_guild(self, trans, guild):
        values = self._guild_values(guild)
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

    # Message
    def add_message(self, trans, message):
        attach_urls = '\n'.join(attach.url for attach in message.attachments)
        if message.content:
            content = '\n'.join((message.content, attach_urls))
        else:
            content = attach_urls

        self.logger.info(f"Inserting message {message.id}")
        values = self._message_values(message)
        values['content'] = content
        ins = self.tb_messages \
                .insert() \
                .values(values)
        trans.execute(ins)

    def edit_message(self, trans, before, after):
        self.logger.info(f"Updating message {after.id}")
        upd = self.tb_messages \
                .update() \
                .values({
                    'edit_timestamp': after.edited_at,
                    'is_edited': before.content != after.content,
                    'content': after.content,
                    'embeds': embeds_to_json(after.embeds),
                }) \
                .where(self.tb_messages.c.message_id == after.id)
        trans.execute(upd)

    def remove_message(self, trans, message):
        self.logger.info(f"Deleting message {message.id}")
        upd = self.tb_messages \
                .update() \
                .values({
                    'is_deleted': True,
                }) \
                .where(self.tb_messages.c.message_id == message.id)
        trans.execute(upd)

    def insert_message(self, trans, message):
        self.logger.debug(f"Inserting message {message.id}")
        values = self._message_values(message)
        ins = p_insert(self.tb_messages) \
                .values(values) \
                .on_conflict_do_nothing(index_elements=['message_id'])
        trans.execute(ins)

    # Typing
    def typing(self, trans, channel, user, when):
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

    # Reactions
    def add_reaction(self, trans, reaction, user):
        self.logger.info(f"Inserting reaction for user {user.id} on message {reaction.message.id}")
        ins = self.tb_reactions \
                .insert() \
                .values({
                    'message_id': reaction.message.id,
                    'emoji_id': get_emoji_id(reaction.emoji),
                    'user_id': user.id,
                    'channel_id': reaction.message.channel.id,
                    'guild_id': reaction.message.guild.id,
                })
        trans.execute(ins)

    def remove_reaction(self, trans, reaction, user):
        self.logger.info(f"Deleting reaction for user {user.id} on message {reaction.message.id}")
        delet = self.tb_reactions \
                .delete() \
                .where(self.tb_reactions.c.message_id == reaction.message.id) \
                .where(self.tb_reactions.c.emoji_id == get_emoji_id(reaction.emoji)) \
                .where(self.tb_reactions.c.user_id == user.id)
        trans.execute(delet)

    def clear_reactions(self, trans, message):
        self.logger.info(f"Deleting all reactions on message {message.id}")
        delet = self.tb_reactions \
                .delete() \
                .where(self.tb_reactions.c.message_id == message.id)
        trans.execute(delet)

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
        values = self._role_values(role)
        ins = self.tb_roles \
                .insert() \
                .values(values)
        trans.execute(ins)
        self.role_cache[role.id] = values

    def _update_role(self, trans, role):
        self.logger.info(f"Updating role {role.id} in guild {role.guild.id}")
        values = self._role_values(role)
        upd = self.tb_roles \
                .update() \
                .where(self.tb_roles.c.role_id == role.id) \
                .values(values)
        trans.execute(upd)
        self.role_cache[role.id] = values

    def update_role(self, trans, role):
        if role.id in self.role_cache:
            self._update_role(self, role)
        else:
            self.upsert_role(self, role)

    def remove_role(self, trans, role):
        self.logger.info(f"Deleting role {role.id}")
        upd = self.tb_roles \
                .update() \
                .values(is_deleted=True) \
                .where(self.tb_roles.c.role_id == role.id)
        trans.execute(upd)
        self.role_cache.pop(role.id, None)

    def upsert_role(self, trans, role):
        values = self._role_values(role)
        if self.role_cache.get(role.id) == values:
            self.logger.debug(f"Role lookup for {role.id} is already up-to-date")
            return

        self.logger.info(f"Updating lookup data for role {role.name}")
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
        values = self._channel_values(channel)
        ins = self.tb_channels \
                .insert() \
                .values(values)
        trans.execute(ins)
        self.channel_cache[channel.id] = values

    def _update_channel(self, trans, channel):
        self.logger.info(f"Updating channel {channel.id} in guild {channel.guild.id}")
        values = self._channel_values(channel)
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
        values = self._channel_values(channel)
        if self.channel_cache.get(channel.id) == values:
            self.logger.debug(f"Channel lookup for {channel.id} is already up-to-date")
            return

        self.logger.info(f"Updating lookup data for channel #{channel.name}")
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
        values = self._voice_channel_values(channel)
        ins = self.tb_voice_channels \
                .insert() \
                .values(values)
        trans.execute(ins)
        self.voice_channel_cache[channel.id] = values

    def _update_voice_channel(self, trans, channel):
        self.logger.info(f"Updating voice channel {channel.id} in guild {channel.guild.id}")
        values = self._voice_channel_values(channel)
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
        values = self._voice_channel_values(channel)
        if self.voice_channel_cache.get(channel.id) == values:
            self.logger.debug(f"Voice channel lookup for {channel.id} is already up-to-date")
            return

        self.logger.info(f"Updating lookup data for voice channel '{channel.name}'")
        ups = p_insert(self.tb_voice_channels) \
                .values(values) \
                .on_conflict_do_update(
                        index_elements=['voice_channel_id'],
                        index_where=(self.tb_voice_channels.c.voice_channel_id == channel.id),
                        set_=values,
                )
        trans.execute(ups)
        self.voice_channel_cache[channel.id] = values

    # Users
    def add_user(self, trans, user):
        if user.id in self.user_cache:
            self.logger.debug(f"User {user.id} already inserted.")
            return

        self.logger.info(f"Inserting user {user.id}")
        values = self._user_values(user)
        ins = self.tb_users \
                .insert() \
                .values(values)
        trans.execute(ins)
        self.user_cache[user.id] = values

    def _update_user(self, trans, user):
        self.logger.info(f"Updating user {user.id}")
        values = self._user_values(user)
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
        values = self._user_values(user)
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

        if not isinstance(user, discord.Member):
            return

    # Members
    def add_member(self, trans, member):
        self.logger.info(f"Inserting member data for {member.id}")
        values = self._nick_values(member)
        ins = self.tb_nicknames \
                .insert() \
                .values(values)
        trans.execute(ins)

    def update_member(self, trans, member):
        self.logger.info(f"Updating member data for {member.id}")
        values = {
            'nickname': member.nick,
        }
        upd = self.tb_nicknames \
                .update() \
                .where(and_(
                    self.tb_nicknames.c.user_id == member.id,
                    self.tb_nicknames.c.guild_id == member.guild.id,
                )) \
                .values(values)
        trans.execute(upd)

    def remove_member(self, trans, member):
        self.logger.info(f"Deleting member data for {member.id}")

        # Nothing to do
        pass

    def upsert_member(self, trans, member):
        self.logger.info(f"Upserting member data for {member.id}")
        values = self._nick_values(member)
        ups = p_insert(self.tb_nicknames) \
                .values(values) \
                .on_conflict_do_update(
                        index_elements=['user_id', 'guild_id'],
                        index_where=and_(
                            self.tb_nicknames.c.user_id == member.id,
                            self.tb_nicknames.c.guild_id == member.guild.id,
                        ),
                        set_=values,
                )
        trans.execute(ups)

    # Emojis (TODO)
    def add_emoji(self, trans, emoji):
        # pylint: disable=unreachable
        raise NotImplementedError

        values = self._emoji_values(emoji)
        id = values['emoji_id']
        if id in self.emoji_cache:
            self.logger.debug(f"Emoji {id} already inserted.")
            return

        self.logger.info(f"Inserting emoji {id}")
        ins = self.tb_emojis \
                .insert() \
                .values(id)
        trans.execute(ins)
        self.emoji_cache[id] = values

    def remove_emoji(self, trans, emoji):
        # pylint: disable=unreachable
        raise NotImplementedError

        id = get_emoji_id(emoji)
        self.logger.info(f"Deleting emoji {id}")
        upd = self.tb_emojis \
                .update() \
                .values(is_deleted=True) \
                .where(self.tb_emojis.c.emoji_id == id)
        trans.execute(upd)
        self.emoji_cache.pop(id, None)

    def upsert_emoji(self, trans, emoji):
        # pylint: disable=unreachable
        raise NotImplementedError

        values = self._emoji_values(emoji)
        id = values['emoji_id']
        if self.emoji_cache.get(id) == values:
            self.logger.debug(f"Emoji lookup for {id} is already up-to-date")
            return

        ups = p_insert(self.tb_emojis) \
                .values(values) \
                .on_conflict_do_update(
                        index_elements=['emoji_id'],
                        index_where=(self.tb_emojis.c.emoji_id == id),
                        set_=values,
                    )
        trans.execute(ups)
        self.emoji_cache[id] = values
