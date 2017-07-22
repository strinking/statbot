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
from sqlalchemy.orm import relationship, sessionmaker
import functools

from .message_history import MessageHistory
from .util import null_logger

Column = functools.partial(Column, nullable=False)

__all__ = [
    'DiscordHistoryORM',
]

class DiscordHistoryORM:
    __slots__ = (
        'db',
        'session',
        'logger',
        'table',
    )

    def __init__(self, table_name, db, meta, logger=null_logger):
        Session = sessionmaker(bind=db)

        self.db = db
        self.session = Session()
        self.logger = logger

        self.table = Table(table_name, meta,
                Column('channel_id', BigInteger,
                    ForeignKey('channels.channel_id'), primary_key=True),
                Column('first_message_id', BigInteger,
                    ForeignKey('messages.message_id'), nullable=True),
                Column('ranges',
                    relationship('Range', lazy='dynamic', cascade='all, delete-orphan')))

