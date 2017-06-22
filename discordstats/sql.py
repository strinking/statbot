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

from sqlalchemy import ARRAY, Boolean, Column, Integer, String, Table, Unicode, UnicodeText
from sqlalchemy import MetaData, create_engine

__all__ = [
    'DiscordSqlHandler',
]

def make_addr(config):
    parts = [
        config['database'],
        '://',
    ]

    if config['user']:
        parts.append(config['user'])

        if config['password']:
            parts.append(':')
            parts.append(config['password'])
        parts.append('@')

    parts.append(config['host'])
    parts.append(':')
    parts.append(str(config['port']))
    return ''.join(parts)

class DiscordSqlHandler:
    '''
    An abstract handling class that bridges the gap between
    the SQLAlchemy code and the discord.py code.

    It can correctly handle discord objects and ingest or
    process them into the SQL database accordingly.
    '''

    def __init__(self, config, logger):
        addr = make_addr(config)
        logger.info(f"Opening database: '{addr}'")
        self.db = create_engine(addr, client_encoding='utf8')
        self.meta = MetaData(self.db)
        self.logger = logger

        # Primary tables
        self.tb_messages = Table('messages', self.meta,
                Column('message_id', Integer, primary_key=True),
                Column('is_edited', Boolean),
                Column('is_deleted', Boolean),
                Column('content', UnicodeText),
                Column('author_id', Integer),
                Column('channel_id', Integer),
                Column('server_id', Integer))
        self.tb_reactions = Table('reactions', self.meta,
                Column('message_id', Integer, primary_key=True),
                Column('emoji_id', Integer),
                Column('user_id', Integer))

        # Lookup tables
        self.tb_server_lookup = Table('server_lookup', self.meta,
                Column('server_id', Integer, primary_key=True),
                Column('name', Unicode()),
                Column('channels', ARRAY(Integer)))
        self.tb_channel_lookup = Table('channel_lookup', self.meta,
                Column('channel_id', Integer, primary_key=True),
                Column('name', String()),
                Column('server_id', Integer))
        self.tb_user_lookup = Table('user_lookup', self.meta,
                Column('user_id', Integer, primary_key=True),
                Column('name', Unicode()),
                Column('discriminator', Integer),
                Column('is_bot', Boolean))
        self.tb_emoji_lookup = Table('emoji_lookup', self.meta,
                Column('emoji_id', Integer, primary_key=True),
                Column('name', String()))

        # Create tables
        self.meta.create_all(self.db)

    def ingest_message(self, message):
        ins = self.db.insert()

