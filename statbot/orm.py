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

import asyncio
import functools
from sqlalchemy import BigInteger, Column, ForeignKey, Table
from sqlalchemy.orm import relationship, mapper, sessionmaker

from .message_history import MessageHistory
from .range import Range
from .util import null_logger

Column = functools.partial(Column, nullable=False)

__all__ = [
    'ORMHandler',
]

class MessageHistoryWrap:
    # pylint: disable=no-member

    def __init__(self, cid, mhist):
        self.channel_id = cid
        self.first_message_id = mhist.first

        # This isn't a list, it's a query object
        for range in mhist.ranges:
            self.ranges.append(RangeWrap(cid, range))

    def assign(self, mhist):
        self.first_message_id = mhist.first

        # Replace existing ranges
        i = 0
        for i, (range_wrap, range) in enumerate(zip(self.ranges, mhist.ranges)):
            range_wrap.assign(range)

        # Delete extra ranges
        for range_wrap in self.ranges[i:]:
            self.ranges.remove(range_wrap)

        # Insert remaining ranges
        for range in mhist.ranges[i:]:
            self.ranges.append(RangeWrap(self.channel_id, range))

    def unwrap(self):
        ranges = (range.unwrap() for range in self.ranges)
        return MessageHistory(*ranges, first=self.first_message_id)

class RangeWrap:
    def __init__(self, cid, range):
        self.channel_id = cid
        self.assign(range)

    def assign(self, range):
        self.start_message_id = range.start
        self.end_message_id = range.end

    def unwrap(self):
        return Range(self.start_message_id, self.end_message_id)

class _Transaction:
    __slots__ = (
        'orm',
        'logger',
        'ok',
    )

    def __init__(self, orm):
        self.orm = orm
        self.logger = orm.logger
        self.ok = True

    async def __aenter__(self):
        self.logger.debug("Starting ORM transaction...")
        await self.orm.lock.acquire()
        return self.orm

    async def __aexit__(self, type, value, traceback):
        if (type, value, traceback) == (None, None, None):
            self.logger.debug("Committing ORM transaction...")
            self.orm.session.commit()
        else:
            self.logger.error("Exception occurred in 'with' scope!")
            self.logger.debug("Rolling back ORM transaction...")
            self.ok = False
            self.orm.session.rollback()
        self.orm.lock.release()

class ORMHandler:
    __slots__ = (
        'db',
        'session',
        'lock',
        'logger',

        'tb_channel_hist',
        'tb_ranges_orm',
    )

    def __init__(self, db, meta, logger=null_logger):
        Session = sessionmaker(bind=db)

        self.db = db
        self.session = Session()
        self.lock = asyncio.Lock()
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

    def transaction(self):
        return _Transaction(self)

    def _lookup_message_hist(self, channel):
        # pylint: disable=no-member

        self.logger.info(f"Looking up message history for #{channel.name}")

        return self.session.query(MessageHistoryWrap) \
                .filter(MessageHistoryWrap.channel_id == channel.id) \
                .first()

    def lookup_message_hist(self, channel):
        mhist_wrap = self._lookup_message_hist(channel)

        if mhist_wrap is not None:
            return mhist_wrap.unwrap()
        else:
            return None

    def insert_message_hist(self, channel, mhist):
        self.logger.info(f"Inserting message history for #{channel.name}: {mhist}")
        mhist_wrap = MessageHistoryWrap(channel.id, mhist)
        self.session.add(mhist_wrap)

    def update_message_hist(self, channel, mhist):
        self.logger.info(f"Updating message history for #{channel.name}: {mhist}")
        mhist_wrap = self._lookup_message_hist(channel)
        assert mhist_wrap is not None
        mhist_wrap.assign(mhist)

    def delete_message_hist(self, channel):
        # pylint: disable=no-member

        self.logger.info(f"Deleting message history for #{channel.name}")

        mhist_wrap = self.session.query(MessageHistoryWrap) \
                .filter(MessageHistoryWrap.channel_id == channel.id) \
                .first()
        self.session.delete(mhist_wrap)

    def __del__(self):
        self.session.close()
