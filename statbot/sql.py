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

from sqlalchemy import ARRAY, Boolean, BigInteger, Column, DateTime
from sqlalchemy import Integer, String, Table, Unicode, UnicodeText
from sqlalchemy import MetaData, create_engine
from sqlalchemy.dialects.postgresql import insert as p_insert
import unicodedata

from .util import embeds_to_json, get_emoji_id

__all__ = [
    'DiscordSqlHandler',
]

class _Transaction:
    __slots__ = (
        'sql',
        'logger',
        'trans',
        'conn',
    )

    def __init__(self, sql):
        self.sql = sql
        self.logger = sql.logger
        self.conn = sql.db.connect()
        self.trans = None

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
            self.trans.rollback()

    # For wrapping self.sql methods
    def __getattr__(self, name):
        def wrapped(_, *args, **kwargs):
            kwargs['trans'] = self
            return getattr(self.sql, name)(*args, **kwargs)
        return wrapped

class DiscordSqlHandler:
    '''
    An abstract handling class that bridges the gap between
    the SQLAlchemy code and the discord.py code.

    It can correctly handle discord objects and ingest or
    process them into the SQL database accordingly.
    '''

    __slots__ = (
        'db',
        'meta',
        'logger',

        'tb_messages',
        'tb_reactions',
        'tb_typing',
        'tb_pins',
        'tb_guild_lookup',
        'tb_channel_lookup',
        'tb_user_lookup',
        'tb_emoji_lookup',
        'tb_role_lookup',

        'guild_cache',
        'channel_cache',
        'user_cache',
        'emoji_cache',
        'role_cache',
    )

    def __init__(self, addr, logger):
        logger.info(f"Opening database: '{addr}'")
        self.db = create_engine(addr)
        self.meta = MetaData(self.db)
        self.logger = logger

        # Primary tables
        self.tb_messages = Table('messages', self.meta,
                Column('message_id', BigInteger, primary_key=True),
                Column('is_edited', Boolean),
                Column('is_deleted', Boolean),
                Column('content', UnicodeText),
                Column('embeds', UnicodeText),
                Column('attachments', Integer),
                Column('user_id', BigInteger),
                Column('channel_id', BigInteger),
                Column('guild_id', BigInteger))
        self.tb_reactions = Table('reactions', self.meta,
                Column('message_id', BigInteger),
                Column('emoji_id', BigInteger),
                Column('user_id', BigInteger),
                Column('channel_id', BigInteger),
                Column('guild_id', BigInteger))
        self.tb_typing = Table('typing', self.meta,
                Column('timestamp', DateTime),
                Column('user_id', BigInteger),
                Column('channel_id', BigInteger),
                Column('guild_id', BigInteger))
        self.tb_pins = Table('pins', self.meta,
                Column('pin_id', BigInteger, primary_key=True),
                Column('message_id', BigInteger, primary_key=True),
                Column('pinner_id', BigInteger),
                Column('user_id', BigInteger),
                Column('channel_id', BigInteger),
                Column('guild_id', BigInteger))

        # Lookup tables
        self.tb_guild_lookup = Table('guild_lookup', self.meta,
                Column('guild_id', BigInteger, primary_key=True),
                Column('name', Unicode),
                Column('channels', ARRAY(BigInteger)),
                Column('region',  String))
        self.tb_channel_lookup = Table('channel_lookup', self.meta,
                Column('channel_id', BigInteger, primary_key=True),
                Column('name', String),
                Column('is_deleted', Boolean),
                Column('guild_id', BigInteger))
        self.tb_user_lookup = Table('user_lookup', self.meta,
                Column('user_id', BigInteger, primary_key=True),
                Column('name', Unicode),
                Column('discriminator', Integer),
                Column('is_deleted', Boolean),
                Column('is_bot', Boolean))
        self.tb_emoji_lookup = Table('emoji_lookup', self.meta,
                Column('emoji_id', BigInteger, primary_key=True),
                Column('name', String),
                Column('is_deleted', Boolean),
                Column('category', String),
                Column('unicode', Unicode(1), nullable=True),
                Column('guild_id', BigInteger, nullable=True))
        self.tb_role_lookup = Table('role_lookup', self.meta,
                Column('role_id', BigInteger, primary_key=True),
                Column('name', Unicode),
                Column('color', Integer),
                Column('raw_permissions', BigInteger),
                Column('guild_id', BigInteger),
                Column('is_hoisted', Boolean),
                Column('is_managed', Boolean),
                Column('is_mentionable', Boolean),
                Column('is_deleted', Boolean),
                Column('position', Integer))

        # Lookup caches
        self.guild_cache = {}
        self.channel_cache = {}
        self.user_cache = {}
        self.emoji_cache = {}
        self.role_cache = {}

        # Create tables
        self.meta.create_all(self.db)

    # Transaction logic
    def transaction(self):
        return _Transaction(self)

    def execute(self, trans, *args, **kwargs):
        if trans is None:
            self.db.execute(*args, **kwargs)
        else:
            trans.execute(*args, **kwargs)

    # Value builders
    @staticmethod
    def _guild_values(guild):
        return {
            'guild_id': guild.id,
            'name': guild.name,
            'channels': [channel.id for channel in guild.channels],
            'region': str(guild.region),
        }

    @staticmethod
    def _channel_values(channel):
        return {
            'channel_id': channel.id,
            'name': channel.name,
            'is_deleted': False,
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
    def _emoji_values(emoji):
        if type(emoji) == str:
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
    def upsert_guild(self, guild, trans=None):
        values = self._guild_values(guild)
        if self.guild_cache.get(guild.id) == values:
            self.logger.debug(f"Guild lookup for {guild.id} is already up-to-date")
            return

        self.logger.info(f"Updating lookup data for guild {guild.name}")
        ups = p_insert(self.tb_guild_lookup) \
                .values(values) \
                .on_conflict_do_update(
                        index_elements=['guild_id'],
                        index_where=(self.tb_guild_lookup.c.guild_id == guild.id),
                        set_=values,
                )
        self.execute(trans, ups)
        self.guild_cache[guild.id] = values

    # Message
    def add_message(self, message, trans=None):
        attach_urls = '\n'.join((attach.url for attach in message.attachments))
        if message.content:
            content = '\n'.join((message.content, attach_urls))
        else:
            content = attach_urls

        self.logger.info(f"Inserting message {message.id}")
        ins = self.tb_messages \
                .insert() \
                .values({
                    'message_id': message.id,
                    'is_edited': False,
                    'is_deleted': False,
                    'content': content,
                    'embeds': embeds_to_json(message.embeds),
                    'attachments': len(message.attachments),
                    'user_id': message.author.id,
                    'channel_id': message.channel.id,
                    'guild_id': message.guild.id,
                })
        self.execute(trans, ins)

        self.upsert_guild(message.guild, trans)
        self.upsert_channel(message.channel, trans)
        self.upsert_user(message.author, trans)

    def edit_message(self, before, after, trans=None):
        self.logger.info(f"Updating message {after.id}")
        upd = self.tb_messages \
                .update() \
                .values({
                    'is_edited': before.content != after.content,
                    'content': after.content,
                    'embeds': embeds_to_json(after.embeds),
                }) \
                .where(self.tb_messages.c.message_id == after.id)
        self.execute(trans, upd)

    def remove_message(self, message, trans=None):
        self.logger.info(f"Deleting message {message.id}")
        upd = self.tb_messages \
                .update() \
                .values({
                    'is_deleted': True,
                }) \
                .where(self.tb_messages.c.message_id == message.id)
        self.execute(trans, upd)

        self.upsert_guild(message.guild, trans)
        self.upsert_channel(message.channel, trans)
        self.upsert_user(message.author, trans)

    # Typing
    def typing(self, channel, user, when, trans=None):
        self.logger.info(f"Inserting typing event for user {user.id}")
        ins = self.tb_typing \
                .insert() \
                .values({
                    'timestamp': when,
                    'user_id': user.id,
                    'channel_id': channel.id,
                    'guild_id': channel.guild.id,
                })
        self.execute(trans, ins)

        self.upsert_guild(channel.guild, trans)
        self.upsert_channel(channel, trans)
        self.upsert_user(user, trans)

    # Reactions
    def add_reaction(self, reaction, user, trans=None):
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
        self.execute(trans, ins)

        self.upsert_guild(reaction.message.guild, trans)
        self.upsert_channel(reaction.message.channel, trans)
        self.upsert_user(user, trans)

    def remove_reaction(self, reaction, user, trans=None):
        self.logger.info(f"Deleting reaction for user {user.id} on message {reaction.message.id}")
        delet = self.tb_reactions \
                .delete() \
                .where(self.tb_reactions.c.message_id == reaction.message.id) \
                .where(self.tb_reactions.c.emoji_id == get_emoji_id(reaction.emoji)) \
                .where(self.tb_reactions.c.user_id == user.id)
        self.execute(trans, delet)

        self.upsert_guild(reaction.message.guild, trans)
        self.upsert_channel(reaction.message.channel, trans)
        self.upsert_user(user, trans)

    def clear_reactions(self, message, trans=None):
        self.logger.info(f"Deleting all reactions on message {message.id}")
        delet = self.tb_reactions \
                .delete() \
                .where(self.tb_reactions.c.message_id == reaction.message.id)
        self.execute(trans, delet)

    # Pins (TODO)
    def add_pin(self, announce, message, trans=None):
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
        self.execute(trans, ins)

    def remove_pin(self, announce, message, trans=None):
        raise NotImplementedError

        self.logger.info(f"Deleting pin for message {message.id}")
        delet = self.tb_pins \
                .delete() \
                .where(self.tb_pins.c.pin_id == announce.id) \
                .where(self.tb_pins.c.message_id == message.id)
        self.execute(trans, delet)

    # Roles
    def add_role(self, role, trans=None):
        if role.id in self.role_cache:
            self.logger.debug(f"Role {role.id} already inserted.")
            return

        self.logger.info(f"Inserting role {role.id}")
        values = self._role_values(role)
        ins = self.tb_role_lookup \
                .insert() \
                .values(values)
        self.execute(trans, ins)
        self.role_cache[role.id] = values

        self.upsert_guild(role.guild)

    def remove_role(self, role, trans=None):
        self.logger.info(f"Deleting role {role.id}")
        upd = self.tb_role_lookup \
                .update() \
                .values(is_deleted=True) \
                .where(self.tb_role_lookup.c.role_id == role.id)
        self.execute(trans, upd)
        self.role_cache.pop(role.id, None)

        self.upsert_guild(role.guild, trans)

    def upsert_role(self, role, trans=None):
        values = self._role_values(role)
        if self.role_cache.get(role.id) == values:
            self.logger.debug(f"Role lookup for {role.id} is already up-to-date")
            return

        self.logger.info("Updating lookup data for role {role.name}")
        ups = p_insert(self.tb_role_lookup) \
                .values(values) \
                .on_conflict_do_update(
                        index_elements=['role_id'],
                        index_where=(self.tb_role_lookup.c.role_id == role.id),
                        set_=values,
                )
        self.execute(trans, ups)
        self.role_cache[role.id] = values

        self.upsert_guild(role.guild, trans)

    # Channels
    def add_channel(self, channel, trans=None):
        if channel.id in self.channel_cache:
            self.logger.debug(f"Channel {channel.id} already inserted.")
            return

        self.logger.info(f"Inserting new channel {channel.id} for guild {guild.id}")
        values = self._channel_values(channel)
        ins = self.tb_channel_lookup \
                .insert() \
                .values(values)
        self.execute(trans, ins)
        self.channel_cache[channel.id] = values

    def _update_channel(self, channel, trans):
        self.logger.info(f"Updating channel {channel.id} in guild {guild.id}")
        values = self._channel_values(channel)
        upd = self.tb_channel_lookup \
                .update() \
                .where(self.tb_channel_lookup.c.channel_id == channel.id) \
                .values(values)
        self.execute(upd)
        self.channel_cache[channel.id] = values

    def update_channel(self, channel, trans=None):
        if channel.id in self.channel_cache.keys():
            self._update_channel(channel, trans)
        else:
            self.upsert_channel(channel, trans)

    def remove_channel(self, channel, trans=None):
        self.logger.info(f"Deleting channel {channel.id} in guild {guild.id}")
        upd = self.tb_channel_lookup \
                .update() \
                .values(is_deleted=True) \
                .where(self.tb_channel_lookup.c.channel_id == channel.id)
        self.execute(upd)
        self.channel_cache.pop(channel.id, None)

    def upsert_channel(self, channel, trans=None):
        values = self._channel_values(channel)
        if self.channel_cache.get(channel.id) == values:
            self.logger.debug(f"Channel lookup for {channel.id} is already up-to-date")
            return

        self.logger.info(f"Updating lookup data for channel {channel.name}")
        ups = p_insert(self.tb_channel_lookup) \
                .values(values) \
                .on_conflict_do_update(
                        index_elements=['channel_id'],
                        index_where=(self.tb_channel_lookup.c.channel_id == channel.id),
                        set_=values,
                )
        self.execute(trans, ups)
        self.channel_cache[channel.id] = values

    # Users
    def add_user(self, user, trans=None):
        if user.id in self.user_cache:
            self.logger.debug(f"User {user.id} already inserted.")
            return

        self.logger.info(f"Inserting user {user.id}")
        values = self._user_values(user)
        ins = self.tb_user_lookup \
                .insert() \
                .values(values)
        self.execute(trans, ins)
        self.user_cache[user.id] = values

    def _update_user(self, user, trans):
        self.logger.info(f"Updating user {user.id}")
        values = self._user_values(user)
        upd = self.tb_user_lookup \
                .update() \
                .where(self.tb_user_lookup.c.user_id == user.id) \
                .values(values)
        self.execute(trans, upd)
        self.user_cache[user.id] = values

    def update_user(self, user, trans=None):
        if user.id in self.user_cache.keys():
            self._update_user(user, trans)
        else:
            self.upsert_user(user, trans)

    def remove_user(self, user, trans=None):
        self.logger.info(f"Removing user {user.id}")
        upd = self.tb_user_lookup \
                .update() \
                .values(is_deleted=True) \
                .where(self.tb_user_lookup.c.user_id == user.id)
        self.execute(upd)
        self.user_cache.pop(user.id, None)

    def upsert_user(self, user, trans=None):
        values = self._user_values(user)
        if self.user_cache.get(user.id) == values:
            self.logger.debug(f"User lookup for {user.id} is already up-to-date")
            return

        ups = p_insert(self.tb_user_lookup) \
                .values(values) \
                .on_conflict_do_update(
                        index_elements=['user_id'],
                        index_where=(self.tb_user_lookup.c.user_id == user.id),
                        set_=values,
                )
        self.execute(trans, ups)
        self.user_cache[user.id] = values

    # Emojis (TODO)
    def add_emoji(self, emoji, trans=None):
        raise NotImplementedError

        values = self._emoji_values(emoji)
        id = values['emoji_id']
        if id in self.emoji_cache:
            self.logger.debug(f"Emoji {id} already inserted.")
            return

        self.logger.info(f"Inserting emoji {id}")
        ins = self.tb_emoji_lookup \
                .insert() \
                .values(value)
        self.execute(trans, ins)
        self.emoji_cache[id] = values

    def remove_emoji(self, emoji, trans=None):
        raise NotImplementedError

        id = get_emoji_id(emoji)
        self.logger.info(f"Deleting emoji {id}")
        upd = self.tb_emoji_lookup \
                .update() \
                .values(is_deleted=True) \
                .where(self.tb_emoji_lookup.c.emoji_id == id)
        self.execute(trans, upd)
        self.emoji_cache.pop(id, None)

    def upsert_emoji(self, emoji, trans=None):
        raise NotImplementedError

        values = self._emoji_values(emoji)
        id = values['emoji_id']
        if self.emoji_cache.get(id) == values:
            self.logger.debug(f"Emoji lookup for {id} is already up-to-date")
            return

        ups = p_insert(self.tb_emoji_lookup) \
                .values(values) \
                .on_conflict_do_update(
                        index_elements=['emoji_id'],
                        index_where=(self.tb_emoji_lookup.c.emoji_id == id),
                        set_=values,
                    )
        self.execute(trans, ups)
        self.emoji_cache[id] = values

