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

from sqlalchemy import ARRAY, Boolean, BigInteger, Column, String, Table, Unicode, UnicodeText
from sqlalchemy import MetaData, create_engine

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
        self.db = create_engine(addr, client_encoding='utf8')
        self.meta = MetaData(self.db)
        self.logger = logger

        # Primary tables
        self.tb_messages = Table('messages', self.meta,
                Column('message_id', BigInteger, primary_key=True),
                Column('is_edited', Boolean),
                Column('is_deleted', Boolean),
                Column('content', UnicodeText),
                Column('author_id', BigInteger),
                Column('channel_id', BigInteger),
                Column('server_id', BigInteger))
        self.tb_reactions = Table('reactions', self.meta,
                Column('message_id', BigInteger, primary_key=True),
                Column('emoji_id', BigInteger),
                Column('user_id', BigInteger))

        # Lookup tables
        self.tb_server_lookup = Table('server_lookup', self.meta,
                Column('server_id', BigInteger, primary_key=True),
                Column('name', Unicode()),
                Column('channels', ARRAY(BigInteger)),
                Column('region',  String()))
        self.tb_channel_lookup = Table('channel_lookup', self.meta,
                Column('channel_id', BigInteger, primary_key=True),
                Column('name', String()),
                Column('server_id', BigInteger))
        self.tb_user_lookup = Table('user_lookup', self.meta,
                Column('user_id', BigInteger, primary_key=True),
                Column('name', Unicode()),
                Column('discriminator', BigInteger),
                Column('is_bot', Boolean))
        self.tb_emoji_lookup = Table('emoji_lookup', self.meta,
                Column('emoji_id', BigInteger, primary_key=True),
                Column('name', String()))

        # Create tables
        self.meta.create_all(self.db)

    def add_message(self, message):
        ins = self.tb_messages.insert()
        ins.values({
            'message_id': message.id,
            'is_edited': False,
            'is_deleted': False,
            'content': message.content,
            'author_id': message.author.id,
            'channel_id': message.channel.id,
            'server_id': message.server.id,
        })
        self.db.execute(ins)

    def edit_message(self, message):
        upd = self.tb_messages.update()
        upd.values({
            'is_edited': True,
            'content': message.content,
        })
        upd.where(self.tb_messages.c.message_id == message.id)
        self.db.execute(upd)

    def delete_message(self, message):
        upd = self.tb_messages.update()
        upd.values({
            'is_deleted': True,
        })
        upd.where(self.tb_messages.c.message_id == message.id)
        self.db.execute(upd)

    def add_reaction(self, reaction, user):
        ins = self.tb_reactions.insert()
        ins.values({
            'message_id': reaction.message.id,
            'emoji_id': reaction.emoji.id,
            'user_id': user.id,
        })
        self.db.execute(ins)

        self.tb_reactions = Table('reactions', self.meta,
                Column('message_id', Integer, primary_key=True),
                Column('emoji_id', Integer),
                Column('user_id', Integer))

    def delete_reaction(self, reaction, user):
        delet = self.tb_reactions.delete()
        delet.where(self.tb_reactions.c.message_id == reaction.message.id)
        delet.where(self.tb_reactions.c.user_id == user.id)
        self.db.execute(delet)

    def clear_reactions(self, message):
        delet = self.tb_reactions.delete()
        delet.where(self.tb_reactions.c.message_id == reaction.message.id)
        self.db.execute(delet)

