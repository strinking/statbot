#
# client.py
#
# discord-analytics - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# discord-analytics is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import discord

__all__ = [
    'AnalyticsClient',
]

from .sql import DiscordSqlHandler
from .util import null_logger

class AnalyticsClient(discord.client):
    def __init__(self, config, logger=null_logger):
        self.config = config
        self.sql = DiscordSqlHandler(config['url'], logger)
        self.logger = logger
        self.ready = False

    def _accept(self, message):
        if not self.ready:
            self.logger.warn("Can't log message, not ready yet!")
            return False
        elif not isinstance(message.channel, discord.TextChannel):
            self.logger.debug("Message not from a guild.")
            self.logger.debug("Ignoring message.")
        elif not message.guild.id not in self.config['guilds']:
            self.logger.debug("Message from a guild we don't care about.")
            self.logger.debug("Ignoring message.")
            return False
        else:
            return True

    def _log(self, message, action):
        #TODO
        author = f"{message.author.name}#{message.author.discriminator}"
        logger.info(f"Message from {author} in {message.server.name} #{message.channel.name} {action}: {message.content}")

    @bot.async_event
    async def on_ready(self):
        # Print welcome string
        logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")

        # All done setting up
        logger.info("Ready!")
        bot.ready = True

    @bot.async_event
    async def on_message(self, message):
        logger.debug(f"Message id {message.id} created")
        if not accept_message(message):
            return

        log_message(message, 'created')
        bot.sql.add_message(message)

    @bot.async_event
    async def on_message_edit(self, message):
        logger.debug(f"Message id {message.id} edited")
        if not accept_message(message):
            return

        log_message(message, 'edited')
        bot.sql.edit_message(message)

    @bot.async_event
    async def on_message_delete(self, message):
        logger.debug(f"Message id {message.id} deleted")
        if not accept_message(message):
            return

        log_message(message, 'deleted')
        bot.sql.delete_message(message)

    @bot.async_event
    async def on_reaction_add(self, reaction, user):
        logger.debug(f"Reaction {reaction.emoji.name} added")
        if not accept_message(reaction.message):
            return

        bot.sql.add_reaction(reaction, user)

    @bot.async_event
    async def on_reaction_remove(self, reaction, user):
        logger.debug(f"Reaction {reaction.emoji.name} added")
        if not accept_message(reaction.message):
            return

        bot.sql.delete_reaction(reaction, user)

    @bot.async_event
    async def on_reaction_clear(self, message, reactions):
        logger.debug(f"Reactions from {message.id} cleared")
        if not accept_message(message):
            return

        bot.sql.clear_reactions(message)

