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
import abc
import asyncio
import discord

from .util import null_logger

__all__ = [
    'AbstractCrawler',
    'HistoryCrawler',
    'AuditLogCrawler',
]

NOW_ID = discord.utils.time_snowflake(datetime.now())

class AbstractCrawler:
    __slots__ = (
        'name',
        'client',
        'sql',
        'config',
        'logger',
        'progress',
        'queue',
    )

    def __init__(self, name, client, sql, config, logger=null_logger):
        self.name = name
        self.client = client
        self.sql = sql
        self.config = config
        self.logger = logger
        self.progress = {} # { stream : last_id }
        self.queue = asyncio.Queue(self.config['crawler']['queue-size'])

    @abc.abstractmethod
    async def init(self):
        pass

    @abc.abstractmethod
    async def read(self, source, last_id):
        pass

    @abc.abstractmethod
    async def write(self, trans, events):
        pass

    def start(self):
        self.client.loop.create_task(self.producer())
        self.client.loop.create_task(self.consumer())

    async def producer(self):
        self.logger.info(f"{self.name}: producer coroutine started!")

        # Setup
        await self.client.wait_until_ready()
        await self.init()

        yield_delay = self.config['crawler']['yield-delay']
        long_delay = self.config['crawler']['empty-source-delay']

        while True:
            done = False
            # Round-robin between all sources:
            # Tuple because the underlying dictionary may change size
            for source, last_id in tuple(self.progress.items()):
                try:
                    done |= await self.read(source, last_id)
                except Exception:
                    self.logger.error(f"Error reading events from source {source}", exc_info=1)

            if done:
                self.logger.info("{self.name}: all sources are exhausted, sleeping for a while...")
                delay = long_delay
            else:
                delay = yield_delay
            await asyncio.sleep(delay)

    async def consumer(self):
        self.logger.info(f"{self.name}: consumer coroutine started!")

        while True:
            events = await self.queue.get()
            self.logger.info("{self.name}: got group of events from queue")

            try:
                with self.sql.transaction() as trans:
                    await self.write(trans, events)
            except Exception:
                self.logger.error(f"{self.name}: error during event write", exc_info=1)

            self.queue.task_done()

class HistoryCrawler(AbstractCrawler):
    def __init__(self, client, sql, config, logger=null_logger):
        AbstractCrawler.__init__(self, 'Channels', client, sql, config, logger)

    @staticmethod
    async def _channel_first(chan):
        async for msg in chan.history(limit=1, after=discord.utils.snowflake_time(0)):
            return msg.id
        return None

    def _channel_ok(self, channel):
        if channel.guild.id in self.config['guilds']:
            return channel.permissions_for(channel.guild.me).read_message_history
        return False

    async def init(self):
        with self.sql.transaction() as trans:
            for guild in self.client.guilds:
                if guild.id in self.config['guilds']:
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).read_message_history:
                            last_id = self.sql.lookup_channel_crawl(trans, channel)
                            if last_id is None:
                                self.sql.insert_channel_crawl(trans, channel, 0)
                            self.progress[channel.id] = last_id

        self.client.hooks['on_guild_channel_create'] = self._channel_create_hook
        self.client.hooks['on_guild_channel_delete'] = self._channel_delete_hook
        self.client.hooks['on_guild_channel_update'] = self._channel_update_hook

    async def read(self, channel, last_id):
        # pylint: disable=arguments-differ
        last = discord.utils.snowflake_time(last_id)
        limit = self.config['crawler']['batch-size']
        self.logger.info(f"Reading through channel {channel.id} ({channel.guild.name} #{channel.name}):")
        self.logger.info(f"Starting from ID {last_id} ({last})")

        messages = await channel.history(after=last, limit=limit).flatten()
        if not messages:
            self.logger.info("No messages found in this range")
            return False

        await self.queue.put(messages)
        self.logger.info(f"Queued {len(messages)} messages for ingestion")
        return True

    async def write(self, trans, messages):
        # pylint: disable=arguments-differ
        for message in messages:
            self.sql.insert_message(trans, message)
            for reaction in message.reactions:
                users = await reaction.users().flatten()
                self.sql.upsert_emoji(trans, reaction.emoji)
                self.sql.insert_reaction(trans, reaction, users)

    async def _channel_create_hook(self, channel):
        if not self._channel_ok(channel) or channel.id in self.progress:
            return

        self.logger.info(f"Adding #{channel.name} to tracked channels")
        self.progress[channel.id] = None

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
            self.progress[after.id] = None
        else:
            self.logger.info(f"Updating #{after.name} - removing from list")
            self.progress.pop(after.id, None)

class AuditLogCrawler(AbstractCrawler):
    def __init__(self, client, sql, config, logger=null_logger):
        AbstractCrawler.__init__(self, 'Audit Log', client, sql, config, logger)

    async def init(self):
        pass

    async def read(self, guild, last_id):
        # pylint: disable=arguments-differ
        pass

    async def write(self, trans, entries):
        # pylint: disable=arguments-differ
        pass
