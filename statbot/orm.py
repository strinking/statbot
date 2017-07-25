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
    'DiscordHistoryORM',
]

class DiscordHistoryORM:
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
                Column('channel_id', BigInteger,
                    ForeignKey('channels.channel_id'), primary_key=True),
                Column('first_message_id', BigInteger,
                    ForeignKey('messages.message_id'), nullable=True),
                Column('ranges', relationship('range_orm',
                    lazy='dynamic', cascade='all, delete, delete-orphan')))

        self.tb_range_orm = Table('range_orm', meta,
                Column('channel_id', BigInteger, ForeignKey('channel_hist.channel_id')),
                Column('start_message_id', BigInteger),
                Column('end_message_id', BigInteger))

