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

import asyncio
import discord
import pickle
import os

from .range import MultiRange, Range
from .util import null_logger

__all__ = [
    'DiscordHistoryCrawler',
]

MESSAGE_BATCH_SIZE = 256
ASYNC_QUEUE_SIZE   = 32

class DiscordHistoryCrawler:
    __slots__ = (
        'client',
        'sql',
        'config',
        'logger',
        'channels',
        'latest',
        'progress',
        'queue',
    )

    @staticmethod
    def _channel_ok(channel):
        return channel.guild.id in self.config['guilds'] \
                and channel.permissions_for(channel.guild.me).read_message_history

    @staticmethod
    async def _get_lastest(channel):
        async for message in channel.history(limit=1):
            return message
        return None

    @staticmethod
    def _find_chunk(latest, mrange):
        current = latest
        for range in reversed(mrange.ranges):
            count = current - range.max()
            if count >= 0:
                return (current, min(count, MESSAGE_BATCH_SIZE))

            current = range.min()
        return (current, MESSAGE_BATCH_SIZE)

    def __init__(self, client, sql, config, logger=null_logger):
        self.client = client
        self.sql = sql
        self.config = config
        self.logger = logger
        self.channels = {} # {channel_id : channel}
        self.latest = {} # {channel_id : Optional[Message]}
        self.progress = {} # {channel_id : MultiRange}
        self.queue = asyncio.Queue(ASYNC_QUEUE_SIZE)

        self._load()

    def _load(self):
        filename = self.config['serial']['filename']
        if not os.path.exists(filename):
            self.logger.warning(f"Progress file {filename} not found. Starting fresh.")
            return

        with open(filename, 'rb') as fh:
            self.progress = pickle.load(fh)

    async def _init_channels(self):
        for guild in self.client.guilds:
            if guild.id in self.config['guilds']:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).read_message_history:
                        self.channels[channel.id] = channel
                        self.latest = await self._get_latest(channel)
                        self.progress.setdefault(channel.id, MultiRange())

        for channel in set(self.progress.keys()) - set(self.channels.keys()):
            del self.progress[channel.id]

    def start(self):
        self.client.add_listener(self, 'on_guild_channel_create')
        self.client.add_listener(self, 'on_guild_channel_delete')
        self.client.add_listener(self, 'on_guild_channel_update')
        self.client.loop.create_task(self.serialize())
        self.client.loop.create_task(self.producer())
        self.client.loop.create_task(self.consumer())

    async def serialize(self):
        # Delay first save
        await asyncio.sleep(5)

        while True:
            filename = self.config['serial']['filename']
            if self.config['serial']['backup']:
                self.logger.info(f"Backing up {filename}...")

                if os.path.exists(filename):
                    try:
                        os.rename(filename, filename + '.bak')
                    except Exception:
                        self.logger.error(f"Error backing up {filename}!", exc_info=1)

            self.logger.info(f"Serializing progress to {filename}...")
            with open(filename, 'wb') as fh:
                pickle.dump(self.progress, fh)

            # Sleep until next save
            await asyncio.sleep(self.config['serial']['periodic-save'])

    async def producer(self):
        # Setup
        await self.client.wait_until_ready()
        await self._init_channels()

        while True:
            # tuple() is necessary since the underlying
            # dict of channels may change size during
            # an iteration
            for cid in tuple(self.progress.keys()):
                # Do round-robin between all the channels
                try:
                    channel = self.channels[cid]
                    mrange = self.progress[cid]
                    await self._read(channel, mrange)
                except Exception:
                    self.logger.error(f"Error reading messages from channel id {cid}", exc_info=1)

    async def _read(self, channel, mrange):
        latest_id = self.latest[channel.id]
        before_id, limit = self._find_chunk(latest_id, mrange)
        before = await self.client.get_message(before_id)

        self.logger.info(f"Reading through channel {channel.id} starting at {before_id} (limit: {limit})")
        prev_id = before_id
        messages = await channel.history(before=before, limit=limit).flatten()

        await self.queue.push(messages)
        self.logger.info(f"Queued {limit} messages for ingestion")

        mrange.add(Range(messages[-1].id, before_id))

    async def consumer(self):
        while True:
            messages = await self.queue.get()
            self.logger.info("Got group of messages from queue")

            try:
                with self.sql.transaction() as trans:
                    for message in messages:
                        self.sql.insert_message(trans, message)
            except Exception:
                self.logger.error(f"Error writing message id {message.id}", exc_info=1)

            await self.queue.task_done()

    async def on_guild_channel_create(self, channel):
        if not self._channel_ok(channel):
            return

        self.logger.info(f"Adding #{channel.name} to tracked channels")
        self.progress.setdefault(channel.id, MultiRange())

    async def on_guild_channel_delete(self, channel):
        self.logger.info(f"Removing #{channel.name} from tracked channels")
        self.progress.pop(channel.id, None)

    async def on_guild_channel_update(self, before, after):
        if not self._channel_ok(before):
            return

        if self._channel_ok(after):
            self.logger.info(f"Updating #{channel.name} - adding to list")
            self.progress.setdefault(channel.id, MultiRange())
        else:
            self.logger.info(f"Updating #{channel.name} - removing from list")
            self.progress.pop(channel.id, None)

