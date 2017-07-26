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
from sqlalchemy.orm import relationship, mapper, sessionmaker
import functools

from .message_history import MessageHistory
from .util import null_logger

Column = functools.partial(Column, nullable=False)

__all__ = [
    'ORMHandler',
]

class MessageHistoryWrap:
    __slots__ = (
        'channel_id',
        'first_message_id',
        'ranges',
    )

    def __init__(self, cid, mhist):
        self.channel_id = cid
        self.first_message_id = mhist.first
        self.ranges = [RangeWrap(cid, range) for range in mhist.ranges]

class RangeWrap:
    __slots__ = (
        'channel_id',
        'start_message_id',
        'end_message_id',
    )

    def __init__(self, cid, range):
        self.channel_id = cid
        self.start_message_id = range.start
        self.end_message_id = range.end

class ORMHandler:
    __slots__ = (
        'db',
        'session',
        'logger',
        'tb_channel_hist',
        'tb_ranges_orm',
    )

    def __init__(self, db, meta, logger=null_logger):
        Session = sessionmaker(bind=db)

        self.db = db
        self.session = Session()
        self.logger = logger

        self.tb_channel_hist = Table('channel_hist', meta,
                Column('channel_id', BigInteger, ForeignKey('channels.channel_id'), primary_key=True),
                Column('first_message_id', BigInteger, ForeignKey('messages.message_id'), nullable=True))
        self.tb_ranges_orm = Table('ranges_orm', meta,
                Column('channel_id', BigInteger, ForeignKey('channel_hist.channel_id'), ondelete='CASCADE'),
                Column('start_message_id', BigInteger, ForeignKey('messages.message_id')),
                Column('end_message_id', BigInteger, ForeignKey('messages.message_id')))

        mapper(MessageHistoryWrap, self.tb_channel_hist, properties={
            'ranges': relationship(RangeWrap,
                lazy='dynamic',
                cascade='all, delete-orphan',
                passive_deletes=True,
            ),
        })
        mapper(RangeWrap, self.tb_ranges_orm)

    def update_message_hist(self, channel, mhist):
        self.logger.info(f"Updating message history for #{channel.name}: {mhist}")
        mhist_wrap = MessageHistoryWrap(channel.id, mhist)

        self.session.add(mhist_wrap)
        self.session.commit()

    def __del__(self):
        self.session.close()

