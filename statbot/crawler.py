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

    def __init__(self, client, sql, config, logger=null_logger):
        self.client = client
        self.sql = sql
        self.config = config
        self.logger = logger
        self.channels = {} # {channel_id : channel}
        self.progress = {} # {channel_id : MessageHistory}
        self.queue = asyncio.Queue(self.config['crawler']['queue-size'])

    async def _init_channels(self):
        with self.sql.transaction() as trans:
            for guild in self.client.guilds:
                if guild.id in self.config['guilds']:
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).read_message_history:
                            self.channels[channel.id] = channel
                            mhist = self.sql.lookup_message_hist(channel)
                            if mhist is None:
                                mhist = MessageHistory()
                                self.sql.insert_message_hist(trans, channel, mhist)
                            self.progress[channel.id] = mhist

        # Remove deleted channels from tracker
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
        await self._init_channels()

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
                    all_empty &= not await self._read(channel, mhist)
                except Exception:
                    self.logger.error(f"Error reading (or syncing) messages from channel id {cid}", exc_info=1)

            # Sleep before next cycle
            if all_empty:
                self.logger.info("All channels are exhausted, sleeping for a while...")
                delay = long_delay
            else:
                delay = yield_delay
            await asyncio.sleep(delay)

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
        if not messages:
            self.logger.info("No messages found in this range")
            return False

        earliest = messages[-1].id
        messages = list(filter(lambda m: m.id not in mhist, messages))
        mhist.add(Range(earliest, start_id))

        if len(messages) < limit:
            # This channel has been exhausted
            self.logger.info(f"#{channel.name} has now been exhausted")
            mhist.first = earliest

        await self.queue.put((channel, mhist, messages))
        self.logger.info(f"Queued {len(messages)} messages for ingestion")
        return True

    async def consumer(self):
        self.logger.info("Consumer coroutine started!")

        while True:
            channel, mhist, messages = await self.queue.get()
            self.logger.info("Got group of messages from queue")

            try:
                with self.sql.transaction() as trans:
                    for message in messages:
                        self.sql.insert_message(trans, message)

                with self.sql.transaction() as trans:
                    self.sql.update_message_hist(trans, channel, mhist)
            except Exception:
                self.logger.error(f"Error writing message id {message.id}", exc_info=1)

            self.queue.task_done()

    async def _channel_create_hook(self, channel):
        if not self._channel_ok(channel) or channel.id in self.progress:
            return

        self.logger.info(f"Adding #{channel.name} to tracked channels")
        mhist = MessageHistory()
        self.progress[channel.id] = mhist

        with self.sql.transaction() as trans:
            self.sql.insert_message_hist(trans, channel, mhist)

    async def _channel_delete_hook(self, channel):
        self.logger.info(f"Removing #{channel.name} from tracked channels")
        self.progress.pop(channel.id, None)

    async def _channel_update_hook(self, before, after):
        if not self._channel_ok(before):
            return

        if self._channel_ok(after):
            if after.id in self.progress:
                return

            self.logger.info(f"Updating #{after.name} - adding to list")
            mhist = MessageHistory()
            self.progress[after.id] = mhist

            with self.sql.transaction() as trans:
                self.sql.insert_message_hist(trans, after, mhist)
        else:
            self.logger.info(f"Updating #{after.name} - removing from list")
            self.progress.pop(after.id, None)

    def _channel_ok(self, channel):
        return channel.guild.id in self.config['guilds'] \
                and channel.permissions_for(channel.guild.me).read_message_history
