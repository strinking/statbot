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

from sqlalchemy import Column, Integer, String

__all__ = [
    'DiscordSqlHandler',
]

Base = declarative_base()

class Table(Base):
    __tablename__ = 'discord_messages'
    id = Column('message_id', Integer, primary_key=True)


class DiscordSqlHandler:
    def __init__(self, path, logger):
        # TODO(path)
        self.logger = logger

