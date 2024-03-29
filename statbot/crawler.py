#
# crawler.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017-2018 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

from datetime import datetime
import abc
import asyncio

from sqlalchemy.exc import SQLAlchemyError
import discord

from .sql import DiscordSqlHandler
from .util import null_logger

__all__ = [
    "AbstractCrawler",
    "HistoryCrawler",
    "AuditLogCrawler",
]


class AbstractCrawler:
    __slots__ = (
        "name",
        "client",
        "sql",
        "config",
        "logger",
        "progress",
        "queue",
        "continuous",
        "current",
    )

    def __init__(
        self,
        name,
        client,
        sql: DiscordSqlHandler,
        config,
        logger=null_logger,
        continuous=False,
    ):
        self.name = name
        self.client = client
        self.sql = sql
        self.config = config
        self.logger = logger
        self.progress = {}  # { stream : last_id }
        self.queue = asyncio.Queue(self.config["crawler"]["queue-size"])
        self.continuous = continuous
        self.current = None

    def _update_current(self):
        self.current = discord.utils.time_snowflake(datetime.now())

    @staticmethod
    def get_last_id(objects):
        # pylint: disable=arguments-differ
        return max(map(lambda x: x.id, objects))

    @abc.abstractmethod
    async def init(self):
        pass

    @abc.abstractmethod
    async def read(self, source, last_id):
        pass

    @abc.abstractmethod
    async def write(self, txact, source, events):
        pass

    @abc.abstractmethod
    async def update(self, txact, source, last_id):
        pass

    def start(self):
        self.client.loop.create_task(self.producer())
        self.client.loop.create_task(self.consumer())

    async def producer(self):
        self.logger.info(f"{self.name}: producer coroutine started!")

        # Setup
        await self.client.wait_until_ready()
        await self.init()

        yield_delay = self.config["crawler"]["delays"]["yield"]
        long_delay = self.config["crawler"]["delays"]["empty-source"]

        done = dict.fromkeys(self.progress.keys(), False)
        while True:
            self._update_current()

            # Round-robin between all sources:
            # Tuple because the underlying dictionary may change size
            for source, last_id in tuple(self.progress.items()):
                if done[source] and not self.continuous:
                    continue

                try:
                    events = await self.read(source, last_id)
                    if events is None:
                        # This source is exhausted
                        done[source] = True
                        await self.queue.put((source, None, self.current))
                        self.progress[source] = self.current
                    else:
                        # This source still has more
                        done[source] = False
                        last_id = self.get_last_id(events)
                        await self.queue.put((source, events, last_id))
                        self.progress[source] = last_id
                except discord.DiscordException:
                    self.logger.error(
                        f"{self.name}: error during event read", exc_info=1
                    )

            if all(done.values()):
                self.logger.info(
                    f"{self.name}: all sources are exhausted, sleeping for a while..."
                )
                delay = long_delay
            else:
                delay = yield_delay
            await asyncio.sleep(delay)

    async def consumer(self):
        self.logger.info(f"{self.name}: consumer coroutine started!")

        while True:
            source, events, last_id = await self.queue.get()
            self.logger.info(f"{self.name}: got group of events from queue")

            try:
                with self.sql.transaction() as txact:
                    if events is not None:
                        await self.write(txact, source, events)
                    await self.update(txact, source, last_id)
            except SQLAlchemyError:
                self.logger.error(f"{self.name}: error during event write", exc_info=1)

            self.queue.task_done()


class HistoryCrawler(AbstractCrawler):
    def __init__(self, client, sql, config, logger=null_logger):
        AbstractCrawler.__init__(self, "Channels", client, sql, config, logger)

    def _channel_ok(self, channel):
        if channel.guild.id in self.config["guild-ids"]:
            return channel.permissions_for(channel.guild.me).read_message_history
        return False

    @staticmethod
    async def _channel_first(chan):
        async for msg in chan.history(limit=1, after=discord.utils.snowflake_time(0)):
            return msg.id
        return None

    async def init(self):
        with self.sql.transaction() as txact:
            for guild in map(self.client.get_guild, self.config["guild-ids"]):
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).read_message_history:
                        last_id = self.sql.lookup_channel_crawl(txact, channel)
                        if last_id is None:
                            self.sql.insert_channel_crawl(txact, channel, 0)
                        self.progress[channel] = last_id or 0

        self.client.hooks["on_guild_channel_create"] = self._channel_create_hook
        self.client.hooks["on_guild_channel_delete"] = self._channel_delete_hook
        self.client.hooks["on_guild_channel_update"] = self._channel_update_hook

    async def read(
        self, channel: discord.TextChannel, last_id
    ) -> list[discord.message.Message]:
        # pylint: disable=arguments-differ
        last = discord.utils.snowflake_time(last_id)
        limit = self.config["crawler"]["batch-size"]
        self.logger.info(
            f"Reading through channel {channel.id} ({channel.guild.name} #{channel.name}):"
        )
        self.logger.info(f"Starting from ID {last_id} ({last})")

        messages = [
            message async for message in channel.history(after=last, limit=limit)
        ]
        if messages:
            self.logger.info(f"Queued {len(messages)} messages for ingestion")
            return messages
        else:
            self.logger.info("No messages found in this range")
            return None

    async def write(self, txact, source, messages):
        # pylint: disable=arguments-differ
        for message in messages:
            self.sql.insert_message(txact, message)
            for reaction in message.reactions:
                try:
                    users = [user async for user in reaction.users()]
                except discord.NotFound:
                    self.logger.warn("Unable to find reaction users", exc_info=1)
                    users = []

                self.sql.upsert_emoji(txact, reaction.emoji)
                self.sql.insert_reaction(txact, reaction, users)

    async def update(self, txact, channel, last_id):
        # pylint: disable=arguments-differ
        self.sql.update_channel_crawl(txact, channel, last_id)

    def _create_progress(self, channel):
        self.progress[channel] = None

        with self.sql.transaction() as txact:
            self.sql.insert_channel_crawl(txact, channel, 0)

    def _update_progress(self, channel):
        with self.sql.transaction() as txact:
            self.sql.update_channel_crawl(txact, channel, self.progress[channel])

    def _delete_progress(self, channel):
        self.progress.pop(channel, None)

        with self.sql.transaction() as txact:
            self.sql.delete_channel_crawl(txact, channel)

    async def _channel_create_hook(self, channel):
        if not self._channel_ok(channel) or channel in self.progress:
            return

        self.logger.info(f"Adding #{channel.name} to tracked channels")
        self._create_progress(channel)

    async def _channel_delete_hook(self, channel):
        self.logger.info(f"Removing #{channel.name} from tracked channels")
        self._delete_progress(channel)

    async def _channel_update_hook(self, before, after):
        if not self._channel_ok(before):
            return

        if self._channel_ok(after):
            if after.id in self.progress:
                return

            self.logger.info(f"Updating #{after.name} - adding to list")
            self._update_progress(after)
        else:
            self.logger.info(f"Updating #{after.name} - removing from list")
            self._delete_progress(after)


class AuditLogCrawler(AbstractCrawler):
    def __init__(self, client, sql, config, logger=null_logger):
        AbstractCrawler.__init__(
            self, "Audit Log", client, sql, config, logger, continuous=True
        )

    async def init(self):
        with self.sql.transaction() as txact:
            for guild in map(self.client.get_guild, self.config["guild-ids"]):
                if guild.me.guild_permissions.view_audit_log:
                    last_id = self.sql.lookup_audit_log_crawl(txact, guild)
                    if last_id is None:
                        self.sql.insert_audit_log_crawl(txact, guild, 0)
                    self.progress[guild] = last_id or 0

    async def read(self, guild: discord.Guild, last_id) -> list[discord.AuditLogEntry]:
        # pylint: disable=arguments-differ
        last = discord.utils.snowflake_time(last_id)
        limit = self.config["crawler"]["batch-size"]
        self.logger.info(f"Reading through {guild.name}'s audit logs")
        self.logger.info(f"Starting from ID {last_id} ({last})")

        # Weirdly, .audit_logs() behaves differently from other history functions.
        # It will give us entries not in our specified range of "after=last".
        # As a simple remedy, we keep on slamming it with requests until it gives
        # us the same list twice in a row, and then we know we're done.
        entries = [entry async for entry in guild.audit_logs(after=last, limit=limit)]
        if entries and self.get_last_id(entries) != last_id:
            self.logger.info(f"Queued {len(entries)} audit log entries for ingestion")
            return entries
        else:
            self.logger.info("No audit log entries found in this range")
            return None

    async def write(self, txact, guild, entries: list[discord.AuditLogEntry]):
        # pylint: disable=arguments-differ
        for entry in entries:
            self.sql.insert_audit_log_entry(txact, guild, entry)

    async def update(self, txact, guild, last_id):
        # pylint: disable=arguments-differ
        self.sql.update_audit_log_crawl(txact, guild, last_id)


class ThreadCrawler(AbstractCrawler):
    def __init__(self, client, sql, config, logger=null_logger):
        AbstractCrawler.__init__(self, "Threads", client, sql, config, logger)

    def _channel_ok(self, channel: discord.TextChannel):
        if channel.guild.id in self.config["guild-ids"]:
            return channel.permissions_for(channel.guild.me).read_message_history
        return False

    def _init_progress_for_thread(self, txact, thread: discord.Thread):
        last_id = self.sql.lookup_thread_crawl(txact, thread)
        if last_id is None:
            self.sql.insert_thread_crawl(txact, thread, 0)
        self.progress[thread] = last_id or 0

    async def init(self):
        with self.sql.transaction() as txact:
            for guild in map(self.client.get_guild, self.config["guild-ids"]):
                for channel in guild.text_channels:
                    if not self._channel_ok(channel):
                        continue

                    # public threads
                    if not channel.permissions_for(guild.me).read_message_history:
                        continue
                    for thread in channel.threads:
                        self._init_progress_for_thread(txact, thread)
                    async for thread in channel.archived_threads(private=False):
                        self._init_progress_for_thread(txact, thread)

                    # private threads
                    if not channel.permissions_for(guild.me).manage_threads:
                        continue
                    async for thread in channel.archived_threads(private=True):
                        self._init_progress_for_thread(txact, thread)

        self.client.hooks["on_thread_create"] = self._thread_create_hook
        self.client.hooks["on_thread_delete"] = self._thread_delete_hook
        self.client.hooks["on_thread_update"] = self._thread_update_hook

    async def read(self, thread: discord.Thread, last_id):
        # pylint: disable=arguments-differ
        last = discord.utils.snowflake_time(last_id)
        limit = self.config["crawler"]["batch-size"]
        self.logger.info(
            f"Reading through thread {thread.id} (guild {thread.guild.name}, #{thread.parent.name}):"
        )
        self.logger.info(f"Starting from ID {last_id} ({last})")

        messages = [
            message async for message in thread.history(after=last, limit=limit)
        ]
        if messages:
            self.logger.info(f"Queued {len(messages)} messages for ingestion")
            return messages
        else:
            self.logger.info("No messages found in this range")
            return None

    async def write(self, txact, source, messages):
        # pylint: disable=arguments-differ
        for message in messages:
            self.sql.insert_message(txact, message)
            for reaction in message.reactions:
                try:
                    users = [user async for user in reaction.users()]
                except discord.NotFound:
                    self.logger.warn("Unable to find reaction users", exc_info=1)
                    users = []

                self.sql.upsert_emoji(txact, reaction.emoji)
                self.sql.insert_reaction(txact, reaction, users)

    async def update(self, txact, thread: discord.Thread, last_id):
        # pylint: disable=arguments-differ
        self.sql.update_thread_crawl(txact, thread, last_id)

    def _create_progress(self, thread: discord.Thread):
        self.logger.info(f"Adding #{thread.name} to tracked threads")

        self.progress[thread] = None

        with self.sql.transaction() as txact:
            self.sql.insert_thread_crawl(txact, thread, 0)

    def _update_progress(self, thread: discord.Thread):
        self.logger.info(f"Updating #{thread.name} in tracked threads")

        with self.sql.transaction() as txact:
            self.sql.update_thread_crawl(txact, thread, self.progress[thread])

    def _delete_progress(self, thread: discord.Thread):
        self.logger.info(f"Removing #{thread.name} from tracked threads")

        self.progress.pop(thread, None)

        with self.sql.transaction() as txact:
            self.sql.delete_thread_crawl(txact, thread)

    async def _thread_create_hook(self, thread: discord.Thread):
        if not self._channel_ok(thread.parent) or thread in self.progress:
            return

        self._create_progress(thread)

    async def _thread_delete_hook(self, thread: discord.Thread):
        self._delete_progress(thread)

    async def _thread_update_hook(self, before: discord.Thread, after: discord.Thread):
        if not self._channel_ok(before.parent):
            return

        if not self._channel_ok(after.parent):
            self._delete_progress(after)
            return

        if after.id in self.progress:
            return

        self._update_progress(after)
