#
# sql.py
#
# discord-analytics - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# discord-analytics is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

from sqlalchemy import ARRAY, Boolean, BigInteger, Column, DateTime
from sqlalchemy import String, Table, Unicode, UnicodeText
from sqlalchemy import MetaData, create_engine
from sqlalchemy.dialects.postgresql import insert as p_insert

from .util import get_emoji_id

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

        # Lookup tables
        self.tb_guild_lookup = Table('guild_lookup', self.meta,
                Column('guild_id', BigInteger, primary_key=True),
                Column('name', Unicode()),
                Column('channels', ARRAY(BigInteger)),
                Column('region',  String()))
        self.tb_channel_lookup = Table('channel_lookup', self.meta,
                Column('channel_id', BigInteger, primary_key=True),
                Column('name', String()),
                Column('guild_id', BigInteger))
        self.tb_user_lookup = Table('user_lookup', self.meta,
                Column('user_id', BigInteger, primary_key=True),
                Column('name', Unicode()),
                Column('discriminator', BigInteger),
                Column('is_bot', Boolean))

        # Lookup caches
        self.guild_cache = {}
        self.channel_cache = {}
        self.user_cache = {}

        # Create tables
        self.meta.create_all(self.db)

    def update_guild(self, guild):
        values = {
            'guild_id': guild.id,
            'name': guild.name,
            'channels': [channel.id for channel in guild.channels],
            'region': str(guild.region),
        }

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

    def update_channel(self, channel):
        values = {
            'channel_id': channel.id,
            'name': channel.name,
            'guild_id': channel.guild.id,
        }

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

    def update_user(self, user):
        values = {
            'user_id': user.id,
            'name': user.name,
            'discriminator': user.discriminator,
            'is_bot': user.bot,
        }

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

    def add_message(self, message):
        ins = self.tb_messages \
                .insert() \
                .values({
                    'message_id': message.id,
                    'is_edited': False,
                    'is_deleted': False,
                    'content': message.content,
                    'user_id': message.author.id,
                    'channel_id': message.channel.id,
                    'guild_id': message.guild.id,
                })
        self.db.execute(ins)

        self.update_guild(message.guild)
        self.update_channel(message.channel)
        self.update_user(message.author)

    def edit_message(self, message):
        upd = self.tb_messages \
                .update() \
                .values({
                    'is_edited': True,
                    'content': message.content,
                }) \
                .where(self.tb_messages.c.message_id == message.id)
        self.db.execute(upd)

        self.update_guild(message.guild)
        self.update_channel(message.channel)
        self.update_user(message.author)

    def delete_message(self, message):
        upd = self.tb_messages \
                .update() \
                .values({
                    'is_deleted': True,
                }) \
                .where(self.tb_messages.c.message_id == message.id)
        self.db.execute(upd)

        self.update_guild(message.guild)
        self.update_channel(message.channel)
        self.update_user(message.author)

    def typing(self, channel, user, when):
        ins = self.tb_typing \
                .insert() \
                .values({
                    'timestamp': when,
                    'user_id': user.id,
                    'channel_id': channel.id,
                    'guild_id': channel.guild.id,
                })
        self.db.execute(ins)

    def add_reaction(self, reaction, user):
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

    def delete_reaction(self, reaction, user):
        delet = self.tb_reactions \
                .delete() \
                .where(self.tb_reactions.c.message_id == reaction.message.id) \
                .where(self.tb_reactions.c.emoji_id == get_emoji_id(reaction.emoji)) \
                .where(self.tb_reactions.c.user_id == user.id)
        self.db.execute(delet)

    def clear_reactions(self, message):
        delet = self.tb_reactions \
                .delete() \
                .where(self.tb_reactions.c.message_id == reaction.message.id)
        self.db.execute(delet)

        self.update_emoji(reaction.emoji)

