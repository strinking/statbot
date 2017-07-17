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
]

class DiscordHistoryCrawler:
    __slots__ = (
        'client',
        'config',
        'logger',
        'progress',
    )

    def __init__(self, client, config, logger=null_logger):
        self.client = client
        self.config = config
        self.logger = logger

        self._load()

    def _load(self):
        filename = self.config['serial']['filename']
        if not os.path.exists(filename):
            self.logger.warning(f"Progress file {filename} not found. Starting fresh.")
            self.progress = {}
            return

        with open(filename, 'rb') as fh:
            self.progress = pickle.load(fh)

    def _init_channels(self):
        channels = set()
        for guild in self.client.guilds:
            if guild.id in self.config['guilds']:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).read_message_history:
                        self.progress.setdefault(channel.id, MultiRange())
                        channels.add(channel.id)

        for channel in set(self.progress.keys()) - channels:
            del self.progress[channel.id]

    def start(self):
        self.client.loop.create_task(self.run())
        self.client.loop.create_task(self.serialize())

    async def run(self):
        await self.client.wait_until_ready()
        self._init_channels()

        while True:
            pass

    async def serialize(self):
        # Delay first save
        await asyncio.sleep(5)

        while True:
            filename = self.config['serial']['filename']
            if self.config['serial']['backup']:
                if os.path.exists(filename)
                    os.rename(filename, filename + '.bak')

            with open(filename, 'wb') as fh:
                pickle.dump(self.progress, fh)

            # Sleep until next save
            await asyncio.sleep(self.config['serial']['periodic-save'])

