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
    'IngestionClient',
]

from .sql import DiscordSqlHandler
from .util import get_username, get_emoji_name, null_logger

class IngestionClient(discord.client):
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
            return False
        elif not message.guild.id not in self.config['guilds']:
            self.logger.debug("Message from a guild we don't care about.")
            self.logger.debug("Ignoring message.")
            return False
        else:
            return True

    def _log(self, message, action):
        name = get_username(message.author)
        guild = message.guild.name
        chan = message.channel.name

        self.logger.info(f"Message from {name} in {guild} #{chan} {action}:")
        self.logger.info(message.content)
        self.logger.info("***")

    def _log_typing(self, channel, user):
        name = get_username(user)
        guild = channel.guild.name
        chan = channel.name

        self.logger.info(f"{name} is typing on {guild} #{chan}")

    def _log_react(self, reaction, user, action):
        name = get_username(user)
        emote = get_emoji_name(reaction.emoji)
        count = reaction.count
        id = reaction.message.id

        self.logger.info(f"{name} {action} {emote} (total {count}) on message id {id}")

    @async_event
    async def on_ready(self):
        # Print welcome string
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")

        # All done setting up
        logger.info("Ready!")
        self.ready = True

    @async_event
    async def on_message(self, message):
        logger.debug(f"Message id {message.id} created")
        if not self._accept(message):
            return

        self._log(message, 'created')
        self.sql.add_message(message)

    @async_event
    async def on_message_edit(self, message):
        logger.debug(f"Message id {message.id} edited")
        if not self._accept(message):
            return

        self._log(message, 'edited')
        self.sql.edit_message(message)

    @async_event
    async def on_message_delete(self, message):
        logger.debug(f"Message id {message.id} deleted")
        if not self._accept(message):
            return

        self._log(message, 'deleted')
        self.sql.delete_message(message)

    @async_event
    async def on_typing(self, channel, user, when):
        logger.debug(f"User id {user.id} is typing")
        if channel.guild.id not in self.config['guilds']:
            return

        self._log_typing(channel, user)
        self.sql.typing(channel, user, when)

    @async_event
    async def on_reaction_add(self, reaction, user):
        logger.debug(f"Reaction {reaction.emoji.name} added")
        if not accept_message(reaction.message):
            return

        self._log_react(reaction, user, 'reacted with')
        self.sql.add_reaction(reaction, user)

    @async_event
    async def on_reaction_remove(self, reaction, user):
        logger.debug(f"Reaction {reaction.emoji.name} removed")
        if not accept_message(reaction.message):
            return

        self._log_react(reaction, user, 'removed a reaction of ')
        self.sql.delete_reaction(reaction, user)

    @async_event
    async def on_reaction_clear(self, message, reactions):
        logger.debug(f"Reactions from {message.id} cleared")
        if not accept_message(message):
            return

        self.logger.info("All reactions on message id {message.id} cleared")
        self.sql.clear_reactions(message)

