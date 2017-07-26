#
# crawler.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

from datetime import datetime
import asyncio
import discord
import os

from .message_history import MessageHistory
from .range import Range
from .util import null_logger

__all__ = [
    'DiscordHistoryCrawler',
]

NOW_ID = discord.utils.time_snowflake(datetime.now())

class DiscordHistoryCrawler:
    __slots__ = (
        'client',
        'sql',
        'config',
        'logger',
        'channels',
        'finished',
        'progress',
        'queue',
    )

    @staticmethod
    def _channel_ok(channel):
        return channel.guild.id in self.config['guilds'] \
                and channel.permissions_for(channel.guild.me).read_message_history

    def __init__(self, client, sql, config, logger=null_logger):
        self.client = client
        self.sql = sql
        self.config = config
        self.logger = logger
        self.channels = {} # {channel_id : channel}
        self.progress = {} # {channel_id : MessageHistory}
        self.queue = asyncio.Queue(self.config['crawler']['queue-size'])

    def _init_channels(self):
        for guild in self.client.guilds:
            if guild.id in self.config['guilds']:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).read_message_history:
                        self.channels[channel.id] = channel
                        self.progress.setdefault(channel.id, MessageHistory())

        for channel in set(self.progress.keys()) - set(self.channels.keys()):
            del self.progress[channel.id]

    def start(self):
        self.client.hooks['on_guild_channel_create'] = self._channel_create_hook
        self.client.hooks['on_guild_channel_delete'] = self._channel_delete_hook
        self.client.hooks['on_guild_channel_update'] = self._channel_update_hook

        self.client.loop.create_task(self.producer())
        self.client.loop.create_task(self.consumer())

    async def producer(self):
        self.logger.info("Producer coroutine started!")

        # Setup
        await self.client.wait_until_ready()
        self._init_channels()

        yield_delay = self.config['crawler']['yield-delay']
        long_delay = self.config['crawler']['long-delay']

        while True:
            # tuple() is necessary since the underlying
            # dict of channels may change size during
            # an iteration
            all_empty = True
            for cid in tuple(self.progress.keys()):
                # Do round-robin between all the channels
                try:
                    channel = self.channels[cid]
                    mhist = self.progress[cid]
                    read = await self._read(channel, mhist)
                    if read:
                        all_empty = False
                        self.sql.orm.update_message_hist(channel, mhist)
                except Exception as ex:
                    if type(ex) == SystemExit:
                        raise ex
                    self.logger.error(f"Error reading (or syncing) messages from channel id {cid}", exc_info=1)

            # Sleep before next cycle
            await asyncio.sleep(long_delay if all_empty else yield_delay)

    async def _read(self, channel, mhist):
        start_id = mhist.find_first_hole(NOW_ID)
        if start_id is None:
            # No more messages in this channel
            return False

        start = discord.utils.snowflake_time(start_id)
        limit = self.config['crawler']['batch-size']
        self.logger.info(f"Reading through channel {channel.id} (#{channel.name}):")
        self.logger.info(f"Starting from {start_id} ({start})")
        messages = await channel.history(before=start, limit=limit).flatten()
        assert messages, "No messages found in this range"

        earliest = messages[-1].id
        messages = list(filter(lambda m: m.id not in mhist, messages))
        if messages: await self.queue.put(messages)
        self.logger.info(f"Queued {len(messages)} messages for ingestion")
        mhist.add(Range(earliest, start_id))

        if len(messages) < limit:
            # This channel has been exhausted
            self.logger.info(f"#{channel.name} has now been exhausted")
            mhist.first = earliest
        return True

    async def consumer(self):
        self.logger.info("Consumer coroutine started!")

        while True:
            messages = await self.queue.get()
            self.logger.info("Got group of messages from queue")

            try:
                with self.sql.transaction() as trans:
                    for message in messages:
                        self.sql.insert_message(trans, message)
            except Exception as ex:
                if type(ex) == SystemExit:
                    raise ex
                self.logger.error(f"Error writing message id {message.id}", exc_info=1)

            self.queue.task_done()

    async def _channel_create_hook(self, channel):
        if not self._channel_ok(channel):
            return

        self.logger.info(f"Adding #{channel.name} to tracked channels")
        self.progress.setdefault(channel.id, MultiRange())

    async def _channel_delete_hook(self, channel):
        self.logger.info(f"Removing #{channel.name} from tracked channels")
        self.progress.pop(channel.id, None)

    async def _channel_update_hook(self, before, after):
        if not self._channel_ok(before):
            return

        if self._channel_ok(after):
            self.logger.info(f"Updating #{channel.name} - adding to list")
            self.progress.setdefault(channel.id, MultiRange())
        else:
            self.logger.info(f"Updating #{channel.name} - removing from list")
            self.progress.pop(channel.id, None)

