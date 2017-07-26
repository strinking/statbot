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
from .range import Range
from .util import null_logger

Column = functools.partial(Column, nullable=False)

__all__ = [
    'ORMHandler',
]

class MessageHistoryWrap(MessageHistory):
    __slots__ = (
        'cid',
    )

    def __init__(self, cid, mhist):
        super().__init__(*mhist.ranges)
        self.first = mhist.first
        self.cid = cid

class RangeWrap(Range):
    __slots__ = (
        'cid',
    )

    def __init__(self, cid, range):
        super().__init__(range.start, range.end)
        self.cid = cid

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

        # Channel history
        self.tb_channel_hist = Table('channel_hist', meta,
                Column('channel_id', BigInteger,
                    ForeignKey('channels.channel_id'), primary_key=True, key='cid'),
                Column('first_message_id', BigInteger,
                    ForeignKey('messages.message_id'), nullable=True, key='first'))
        self.tb_ranges_orm = Table('ranges_orm', meta,
                Column('channel_id', BigInteger,
                    ForeignKey('channel_hist.channel_id'), ondelete='CASCADE', key='cid'),
                Column('start_message_id', BigInteger,
                    ForeignKey('messages.message_id', key='start')),
                Column('end_message_id', BigInteger,
                    ForeignKey('messages.message_id'), key='end'))

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

