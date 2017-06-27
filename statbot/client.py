#
# client.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import discord

__all__ = [
    'LOG_FULL_MESSAGES',
    'make_client',
]

LOG_FULL_MESSAGES = False

from .sql import DiscordSqlHandler
from .util import get_username, get_emoji_name, null_logger

def make_client(config, logger=null_logger):
    client = discord.Client()
    client.ready = False
    sql = DiscordSqlHandler(config['url'], logger)

    def _accept_message(message):
        if not client.ready:
            logger.warn("Can't log message, not ready yet!")
            return False
        elif not hasattr(message, 'guild'):
            logger.debug("Message not from a guild.")
            logger.debug("Ignoring message.")
            return False
        elif getattr(message.guild, 'id', None) not in config['guilds']:
            logger.debug("Message from a guild we don't care about.")
            logger.debug("Ignoring message.")
            return False
        elif message.type != discord.MessageType.default:
            logger.debug("Special type of message receieved.")
            logger.debug("Ignoring message.")
        else:
            return True

    def _accept_channel(channel):
        if not client.ready:
            logger.warn("Can't log event, not ready yet!")
            return False
        elif not hasattr(channel, 'guild'):
            logger.debug("Channel not in a guild.")
            logger.debug("Ignoring message.")
        elif getattr(channel.guild, 'id', None) not in config['guilds']:
            logger.debug("Event from a guild we don't care about.")
            logger.debug("Ignoring message.")
            return False
        else:
            return True

    def _accept_guild(guild):
        if not client.ready:
            logger.warn("Can't log event, not ready yet!")
            return False
        elif getattr(guild, 'id', None) not in config['guilds']:
            logger.debug("Event from a guild we don't care about.")
            logger.debug("Ignoring message.")
            return False
        else:
            return True

    def _log(message, action):
        name = get_username(message.author)
        guild = message.guild.name
        chan = message.channel.name

        logger.info(f"Message {action} by {name} in {guild} #{chan}")
        if LOG_FULL_MESSAGES:
            logger.info("<bom>")
            logger.info(message.content)
            logger.info("<eom>")

    def _log_typing(channel, user):
        name = get_username(user)
        guild = channel.guild.name
        chan = channel.name

        logger.info(f"Typing by {name} on {guild} #{chan}")

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
        if not _accept_message(message):
            return

        _log(message, 'created')
        sql.add_message(message)

    @client.async_event
    async def on_message_edit(before, after):
        logger.debug(f"Message id {after.id} edited")
        if not _accept_message(after):
            return

        _log(after, 'edited')
        sql.edit_message(before, after)

    @client.async_event
    async def on_message_delete(message):
        logger.debug(f"Message id {message.id} deleted")
        if not _accept_message(message):
            return

        _log(message, 'deleted')
        sql.delete_message(message)

    @client.async_event
    async def on_typing(channel, user, when):
        logger.debug(f"User id {user.id} is typing")
        if not _accept_channel(channel):
            return

        _log_typing(channel, user)
        sql.typing(channel, user, when)

    @client.async_event
    async def on_reaction_add(reaction, user):
        logger.debug(f"Reaction {reaction.emoji} added")
        if not _accept_message(reaction.message):
            return

        _log_react(reaction, user, 'reacted with')
        sql.add_reaction(reaction, user)

    @client.async_event
    async def on_reaction_remove(reaction, user):
        logger.debug(f"Reaction {reaction.emoji} removed")
        if not _accept_message(reaction.message):
            return

        _log_react(reaction, user, 'removed a reaction of ')
        sql.delete_reaction(reaction, user)

    @client.async_event
    async def on_reaction_clear(message, reactions):
        logger.debug(f"Reactions from {message.id} cleared")
        if not _accept_message(message):
            return

        logger.info(f"All reactions on message id {message.id} cleared")
        sql.clear_reactions(message)

    @client.async_event
    async def on_guild_channel_create(channel):
        logger.debug(f"Channel was created in guild {channel.guild.id}")
        if not _accept_channel(channel):
            return

        logger.info(f"Channel #{channel.name} created in {channel.guild.name}")
        sql.add_channel(channel)

    @client.async_event
    async def on_guild_channel_delete(channel):
        logger.debug(f"Channel was deleted in guild {channel.guild.id}")
        if not _accept_channel(channel):
            return

        logger.info(f"Channel #{channel.name} deleted in {channel.guild.name}")
        sql.remove_channel(channel)

    @client.async_event
    async def on_guild_channel_update(before, after):
        logger.debug(f"Channel was updated in guild {after.guild.id}")
        if not _accept_channel(after):
            return

        if before.name != after.name:
            changed = f' (now {after.name})'
        else:
            changed = ''
        logger.info(f"Channel #{before.name}{changed} was changed in {after.guild.name}")
        sql.update_channel(before, after)

    @client.async_event
    async def on_guild_channel_pins_update(channel, last_pin):
        logger.debug(f"Channel {channel.id} got a pin update")
        if not _accept_channel(channel):
            return

        logger.info(f"Channel #{channel.name} got a pin update")
        logger.warn("TODO: handling for on_guild_channel_pins_update")

    @client.async_event
    async def on_member_join(member):
        logger.debug(f"Member {member.id} joined guild {member.guild.id}")
        if not _accept_guild(member.guild):
            return

        logger.info(f"Member {member.name} has joined {member.guild.name}")
        sql.add_user(member)

    @client.async_event
    async def on_member_remove(member):
        logger.debug(f"Member {member.id} left guild {member.guild.id}")
        if not _accept_guild(member.guild):
            return

        logger.info(f"Member {member.name} has left {member.guild.name}")
        sql.remove_user(member)

    @client.async_event
    async def on_member_update(before, after):
        logger.debug(f"Member {after.id} was updated in guild {after.guild.id}")
        if not _accept_guild(after.guild):
            return

        if before.name != after.name:
            changed = f' (now {after.name})'
        else:
            changed = ''
        logger.info(f"Member {before.name}{changed} was changed in {after.guild.name}")
        sql.update_user(member)

    @client.async_event
    async def on_guild_join(guild):
        logger.info(f"Just joined guild {guild.name} ({guild.id})")
        logger.info("(Doing nothing)")

    @client.async_event
    async def on_guild_remove(guild):
        logger.info(f"Just left guild {guild.name} ({guild.id})")
        logger.info("(Doing nothing)")

    @client.async_event
    async def on_guild_role_create(role):
        # TODO
        pass

    @client.async_event
    async def on_guild_role_delete(role):
        # TODO
        pass

    @client.async_event
    async def on_guild_role_update(role):
        # TODO
        pass

    @client.async_event
    async def on_guild_emojis_update(guild, before, after):
        before = set(before)
        after = set(before)

        for emoji in after - before:
            sql.add_emoji(emoji)
        for emoji in before - after:
            sql.remove_emoji(emoji)

    # Return client object
    return client

