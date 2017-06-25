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
    'make_client',
]

from .sql import DiscordSqlHandler
from .util import get_username, get_emoji_name, null_logger

def make_client(config, logger=null_logger):
    client = discord.Client()
    client.ready = False
    sql = DiscordSqlHandler(config['url'], logger)

    def _accept(message):
        if not client.ready:
            logger.warn("Can't log message, not ready yet!")
            return False
        elif not isinstance(message.channel, discord.TextChannel):
            logger.debug("Message not from a guild.")
            logger.debug("Ignoring message.")
            return False
        elif message.guild.id not in config['guilds']:
            logger.debug("Message from a guild we don't care about.")
            logger.debug("Ignoring message.")
            return False
        else:
            return True

    def _log(message, action):
        name = get_username(message.author)
        guild = message.guild.name
        chan = message.channel.name

        logger.info(f"Message {action} by {name} in {guild} #{chan}:")
        logger.info(message.content)
        logger.info("<eom>")

    def _log_typing(channel, user):
        name = get_username(user)
        guild = channel.guild.name
        chan = channel.name

        logger.info(f"{name} is typing on {guild} #{chan}")

    def _log_react(reaction, user, action):
        name = get_username(user)
        emote = get_emoji_name(reaction.emoji)
        count = reaction.count
        id = reaction.message.id

        logger.info(f"{name} {action} {emote} (total {count}) on message id {id}")

    @client.async_event
    async def on_ready():
        # Print welcome string
        logger.info(f"Logged in as {client.user.name} ({client.user.id})")
        logger.info("Recording activity in the following guilds:")
        for id in config['guilds']:
            logger.info(f"* {id}")

        # All done setting up
        logger.info("")
        logger.info("Ready!")
        client.ready = True

    @client.async_event
    async def on_message(message):
        logger.debug(f"Message id {message.id} created")
        if not _accept(message):
            return

        _log(message, 'created')
        sql.add_message(message)

    @client.async_event
    async def on_message_edit(before, after):
        logger.debug(f"Message id {after.id} edited")
        if not _accept(after):
            return

        _log(after, 'edited')
        sql.edit_message(after)

    @client.async_event
    async def on_message_delete(message):
        logger.debug(f"Message id {message.id} deleted")
        if not _accept(message):
            return

        _log(message, 'deleted')
        sql.delete_message(message)

    @client.async_event
    async def on_typing(channel, user, when):
        logger.debug(f"User id {user.id} is typing")
        if channel.guild.id not in config['guilds']:
            return

        _log_typing(channel, user)
        sql.typing(channel, user, when)

    @client.async_event
    async def on_reaction_add(reaction, user):
        logger.debug(f"Reaction {reaction.emoji.name} added")
        if not _accept(reaction.message):
            return

        _log_react(reaction, user, 'reacted with')
        sql.add_reaction(reaction, user)

    @client.async_event
    async def on_reaction_remove(reaction, user):
        logger.debug(f"Reaction {reaction.emoji.name} removed")
        if not _accept(reaction.message):
            return

        _log_react(reaction, user, 'removed a reaction of ')
        sql.delete_reaction(reaction, user)

    @client.async_event
    async def on_reaction_clear(message, reactions):
        logger.debug(f"Reactions from {message.id} cleared")
        if not _accept(message):
            return

        logger.info("All reactions on message id {message.id} cleared")
        sql.clear_reactions(message)

    # Return client object
    return client

