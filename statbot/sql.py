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

class DiscordSqlHandler:
    '''
    An abstract handling class that bridges the gap between
    the SQLAlchemy code and the discord.py code.

    It can correctly handle discord objects and ingest or
    process them into the SQL database accordingly.
    '''

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
                Column('guild_id', BigInteger))
        self.tb_user_lookup = Table('user_lookup', self.meta,
                Column('user_id', BigInteger, primary_key=True),
                Column('name', Unicode),
                Column('discriminator', Integer),
                Column('is_bot', Boolean))
        self.tb_emoji_lookup = Table('emoji_lookup', self.meta,
                Column('emoji_id', BigInteger, primary_key=True),
                Column('name', String),
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
                Column('position', Integer))

        # Lookup caches
        self.guild_cache = {}
        self.channel_cache = {}
        self.user_cache = {}
        self.emoji_cache = {}
        self.role_cache = {}

        # Create tables
        self.meta.create_all(self.db)

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
            'guild_id': channel.guild.id,
        }

    @staticmethod
    def _user_values(user):
        return {
            'user_id': user.id,
            'name': user.name,
            'discriminator': user.discriminator,
            'is_bot': user.bot,
        }

    @staticmethod
    def _emoji_values(emoji):
        if type(emoji) == str:
            return {
                'emoji_id': ord(emoji),
                'name': unicodedata.name(emoji),
                'category': unicodedata.category(emoji),
                'unicode': emoji,
                'guild_id': None,
            }
        else:
            return {
                'emoji_id': emoji.id,
                'name': emoji.name,
                'category': '(custom)',
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
            'position': role.position,
        }

    # Guild
    def upsert_guild(self, guild):
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
        self.db.execute(ups)
        self.guild_cache[guild.id] = values

    # Message
    def add_message(self, message):
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
        self.db.execute(ins)

        self.upsert_guild(message.guild)
        self.upsert_channel(message.channel)
        self.upsert_user(message.author)

    def edit_message(self, before, after):
        self.logger.info(f"Updating message {after.id}")
        upd = self.tb_messages \
                .update() \
                .values({
                    'is_edited': before.content != after.content,
                    'content': after.content,
                    'embeds': embeds_to_json(after.embeds),
                }) \
                .where(self.tb_messages.c.message_id == after.id)
        self.db.execute(upd)

    def delete_message(self, message):
        self.logger.info(f"Deleting message {message.id}")
        upd = self.tb_messages \
                .update() \
                .values({
                    'is_deleted': True,
                }) \
                .where(self.tb_messages.c.message_id == message.id)
        self.db.execute(upd)

        self.upsert_guild(message.guild)
        self.upsert_channel(message.channel)
        self.upsert_user(message.author)

    # Typing
    def typing(self, channel, user, when):
        self.logger.info(f"Inserting typing event for user {user.id}")
        ins = self.tb_typing \
                .insert() \
                .values({
                    'timestamp': when,
                    'user_id': user.id,
                    'channel_id': channel.id,
                    'guild_id': channel.guild.id,
                })
        self.db.execute(ins)

        self.upsert_guild(channel.guild)
        self.upsert_channel(channel)
        self.upsert_user(user)

    # Reactions
    def add_reaction(self, reaction, user):
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
        self.db.execute(ins)

        self.upsert_guild(reaction.message.guild)
        self.upsert_channel(reaction.message.channel)
        self.upsert_user(user)
        self.upsert_emoji(reaction.emoji)

    def delete_reaction(self, reaction, user):
        self.logger.info(f"Deleting reaction for user {user.id} on message {message.id}")
        delet = self.tb_reactions \
                .delete() \
                .where(self.tb_reactions.c.message_id == reaction.message.id) \
                .where(self.tb_reactions.c.emoji_id == get_emoji_id(reaction.emoji)) \
                .where(self.tb_reactions.c.user_id == user.id)
        self.db.execute(delet)

        self.upsert_guild(reaction.message.guild)
        self.upsert_channel(reaction.message.channel)
        self.upsert_user(user)
        self.upsert_emoji(reaction.emoji)

    def clear_reactions(self, message):
        self.logger.info(f"Deleting all reactions on message {message.id}")
        delet = self.tb_reactions \
                .delete() \
                .where(self.tb_reactions.c.message_id == reaction.message.id)
        self.db.execute(delet)

    # Pins (TODO)
    def add_pin(self, announce, message):
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
        self.db.execute(ins)

    def remove_pin(self, announce, message):
        raise NotImplementedError

        self.logger.info(f"Deleting pin for message {message.id}")
        delet = self.tb_pins \
                .delete() \
                .where(self.tb_pins.c.pin_id == announce.id) \
                .where(self.tb_pins.c.message_id == message.id)
        self.db.execute(delet)

    # Roles
    def add_role(self, role):
        self.logger.info(f"Inserting role {role.id}")
        values = self._role_values(role)
        ins = self.tb_role_lookup \
                .insert() \
                .values(values)
        self.db.execute(ins)
        self.role_cache[role.id] = values

        self.upsert_guild(role.guild)

    def remove_role(self, role):
        self.logger.info(f"Deleting role {role.id}")
        delet = self.tb_role_lookup \
                .delete() \
                .where(self.tb_role_lookup.c.role_id == role.id)
        self.db.execute(delet)
        self.role_cache.pop(role.id, None)

        self.upsert_guild(role.guild)

    def upsert_role(self, role):
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
        self.db.execute(ups)
        self.role_cache[role.id] = values

        self.upsert_guild(role.guild)

    # Channels
    def add_channel(self, channel):
        self.logger.info(f"Inserting new channel {channel.id} for guild {guild.id}")
        values = self._channel_values(channel)
        ins = self.tb_channel_lookup \
                .insert() \
                .values(values)
        self.db.execute(ins)
        self.channel_cache[channel.id] = values

    def _update_channel(self, channel):
        self.logger.info(f"Updating channel {channel.id} in guild {guild.id}")
        values = self._channel_values(channel)
        upd = self.tb_channel_lookup \
                .update() \
                .where(self.tb_channel_lookup.c.channel_id == channel.id) \
                .values(values)
        self.db.execute(upd)
        self.channel_cache[channel.id] = values

    def update_channel(self, channel):
        if channel.id in self.channel_cache.keys():
            self._update_channel(channel)
        else:
            self.upsert_channel(channel)

    def remove_channel(self, channel):
        self.logger.info(f"Deleting channel {channel.id} in guild {guild.id}")
        delet = self.tb_channel_lookup \
                .delete() \
                .where(self.tb_channel_lookup.c.channel_id == channel.id)
        self.db.execute(delet)
        self.channel_cache.pop(channel.id, None)

    def upsert_channel(self, channel):
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
        self.db.execute(ups)
        self.channel_cache[channel.id] = values

    # Users
    def add_user(self, user):
        self.logger.info(f"Inserting user {user.id}")
        values = self._user_values(user)
        ins = self.tb_user_lookup \
                .insert() \
                .values(values)
        self.db.execute(ins)
        self.user_cache[user.id] = values

    def _update_user(self, user):
        self.logger.info(f"Updating user {user.id}")
        values = self._user_values(user)
        upd = self.tb_user_lookup \
                .update() \
                .where(self.tb_user_lookup.c.user_id == user.id) \
                .values(values)
        self.db.execute(upd)
        self.user_cache[user.id] = values

    def update_user(self, user):
        if user.id in self.user_cache.keys():
            self._update_user(user)
        else:
            self.upsert_user(user)

    def remove_user(self, user):
        self.logger.info(f"Removing user {user.id}")
        delet = self.tb_user_lookup \
                .delete() \
                .where(self.tb_user_lookup.c.user_id == user.id)
        self.db.execute(delet)
        self.user_cache.pop(user.id, None)

    def upsert_user(self, user):
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
        self.db.execute(ups)
        self.user_cache[user.id] = values

    # Emojis
    def add_emoji(self, emoji):
        values = self._emoji_values(emoji)
        id = values['emoji_id']
        self.logger.info(f"Inserting emoji {id}")
        ins = self.tb_emoji_lookup \
                .insert() \
                .values(value)
        self.db.execute(ins)
        self.emoji_cache[id] = values

    def remove_emoji(self, emoji):
        id = get_emoji_id(emoji)
        self.logger.info(f"Deleting emoji {id}")
        delet = self.tb_emoji_lookup \
                .delete() \
                .where(self.tb_emoji_lookup.c.emoji_id == id)
        self.db.execute(delet)
        self.emoji_cache.pop(id, None)

    def upsert_emojis(self, emoji):
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
        self.db.execute(ups)
        self.emoji_cache[id] = values

