#
# orm.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

from sqlalchemy import BigInteger, Column, Table
from sqlalchemy import ForeignKey
from sqlalchemy.orm import backref, relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import functools

from .message_history import MessageHistory
from .util import null_logger

Column = functools.partial(Column, nullable=False)
Base = declarative_base()

__all__ = [
    'DiscordHistory',
]

class DiscordHistoryTable(Base):
    __tablename__ = 'channel_hist'

    channel_id = Column(BigInteger, ForeignKey('channels.channel_id'), primary_key=True)
    first_message_id = Column(BigInteger, ForeignKey('messages.message_id'), nullable=True)
    ranges = relationship(
            'Ranges',
            cascade='all, delete-orphan')

    def __init__(self, mhist):
        self.first_message_id = mhist.first

    def __repr__(self):
        return "<DiscordHistory(channel_id={}, first_message_id={}, ranges={})>".format(
                self.channel_id, self.first_message_id, self.ranges)

class RangeTable(Base):
    __tablename__ = 'ranges_orm'

    channel_id = Column(BigInteger, ForeignKey('channel_hist.channel_id'))
    start_message_id = Column(BigInteger)
    end_message_id = Column(BigInteger)

    def __init__(self, start, end):
        self.start_message_id = start
        self.end_message_id = end

    def __repr__(self):
        return "<DiscordHistory.Range(start_message_id={}, end_message_id={})>".format(
                self.start_message_id, self.end_message_id)

class DiscordHistoryORM:
    __slots__ = (
        'db',
        'session',
        'logger',
        'tb_channel_hist',
        'tb_ranges_orm',
    )

    def __init__(self, db, logger=null_logger):
        Session = sessionmaker(bind=db)

        self.db = db
        self.session = Session()
        self.logger = logger

        self.tb_channel_hist = DiscordHistoryTable
        self.tb_ranges_orm = RangeTable

    def create_tables(self):
        Base.metadata.create_all(self.db)

