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

from sqlalchemy import BigInteger, Column, Integer, Table
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
    def __init__(self, cid, mhist):
        self.channel_id = cid
        self.first_message_id = mhist.first

        # This isn't a list, it's a query object
        for range in mhist.ranges:
            self.ranges.append(RangeWrap(cid, range))

class RangeWrap:
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

        self.logger.info("Initializing ORMHandler...")

        # Channel history
        self.tb_channel_hist = Table('channel_hist', meta,
                Column('channel_id', BigInteger,
                    ForeignKey('channels.channel_id'), primary_key=True),
                Column('first_message_id', BigInteger, nullable=True))
        self.tb_ranges_orm = Table('ranges_orm', meta,
                Column('channel_id', BigInteger,
                    ForeignKey('channel_hist.channel_id', ondelete='CASCADE'),
                    primary_key=True),
                Column('start_message_id', BigInteger, primary_key=True),
                Column('end_message_id', BigInteger))

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

        try:
            self.session.add(mhist_wrap)
            self.session.commit()
        except:
            self.session.rollback()
            raise

    def __del__(self):
        self.session.close()

