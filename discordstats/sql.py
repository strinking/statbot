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
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

__all__ = [
    'DiscordSqlHandler',
]

Base = declarative_base()

class MessageTable(Base):
    __tablename__ = 'messages'
    id = Column('message_id', Integer, primary_key=True)
    edited = Column('is_edited', Boolean)
    deleted = Column('is_deleted', Boolean)
    content = Column('content', UnicodeText)
    author = Column('author_id', Integer)
    channel = Column('channel_id', Integer)
    server = Column('server_id', Integer)

class ReactionTable(Base):
    __tablename__ = 'reactions'
    id = Column('message_id', Integer, primary_key=True)
    emoji = Column('emoji_id', Integer)
    user = Column('user_id', Integer)

class ServerLookupTable(Base):
    __tablename__ = 'server_lookup'
    id = Column('server_id', Integer, primary_key=True)
    name = Column('name', Unicode(100))
    channels = Column('channels', ARRAY(Integer))

class ChannelLookupTable(Base):
    __tablename__ = 'channel_lookup'
    id = Column('channel_id', Integer, primary_key=True)
    name = Column('name', String(100))
    server = Column('server_id', Integer)

class UserLookupTable(Base):
    __tablename__ = 'user_lookup'
    id = Column('user_id', Integer, primary_key=True)
    name = Column('name', Unicode(100))
    discriminator = Column('discriminator', Integer)

class EmojiLookupTable(Base):
    __tablename__ = 'emoji_lookup'
    id = Column('emoji_id', Integer, primary_key=True)
    name = Column('name', String(50))

class DiscordSqlHandler:
    def __init__(self, path, logger):
        # TODO(path)
        self.logger = logger

    def ingest_message(self, message):
        pass

