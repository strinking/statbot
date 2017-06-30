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
    'EventIngestionClient',
]

LOG_FULL_MESSAGES = False

from .sql import DiscordSqlHandler
from .util import get_emoji_name, null_logger

class EventIngestionClient(discord.Client):
    __slots__ = (
        'config',
        'logger',
        'sql',
        'ready',
    )

    def __init__(self, config, logger=null_logger, sql_logger=null_logger):
        super().__init__()
        self.config = config
        self.logger = logger
        self.sql = DiscordSqlHandler(config['url'], sql_logger)
        self.ready = False

    def run(self):
        # Override function to include the token from config
        return super().run(self.config['token'], bot=self.config['bot'])

    def _accept_message(self, message):
        if not self.ready:
            self.logger.warn("Can't log message, not ready yet!")
            return False
        elif not hasattr(message, 'guild'):
            self.logger.debug("Message not from a guild.")
            self.logger.debug("Ignoring message.")
            return False
        elif getattr(message.guild, 'id', None) not in self.config['guilds']:
            self.logger.debug("Message from a guild we don't care about.")
            self.logger.debug("Ignoring message.")
            return False
        elif message.type != discord.MessageType.default:
            self.logger.debug("Special type of message receieved.")
            self.logger.debug("Ignoring message.")
        else:
            return True

    def _accept_channel(self, channel):
        if not self.ready:
            self.logger.warn("Can't log event, not ready yet!")
            return False
        elif not hasattr(channel, 'guild'):
            self.logger.debug("Channel not in a guild.")
            self.logger.debug("Ignoring message.")
        elif getattr(channel.guild, 'id', None) not in self.config['guilds']:
            self.logger.debug("Event from a guild we don't care about.")
            self.logger.debug("Ignoring message.")
            return False
        else:
            return True

    def _accept_guild(self, guild):
        if not self.ready:
            self.logger.warn("Can't log event, not ready yet!")
            return False
        elif getattr(guild, 'id', None) not in self.config['guilds']:
            self.logger.debug("Event from a guild we don't care about.")
            self.logger.debug("Ignoring message.")
            return False
        else:
            return True

    def _log(self, message, action):
        name = message.author.display_name
        guild = message.guild.name
        chan = message.channel.name

        self.logger.info(f"Message {action} by {name} in {guild} #{chan}")
        if LOG_FULL_MESSAGES:
            self.logger.info("<bom>")
            self.logger.info(message.content)
            self.logger.info("<eom>")

    def _log_typing(self, channel, user):
        name = user.display_name
        guild = channel.guild.name
        chan = channel.name

        self.logger.info(f"Typing by {name} on {guild} #{chan}")

    def _log_react(self, reaction, user, action):
        name = user.display_name
        emote = get_emoji_name(reaction.emoji)
        count = reaction.count
        id = reaction.message.id

        self.logger.info(f"{name} {action} {emote} (total {count}) on message id {id}")

    async def on_ready(self):
        # Print welcome string
        self.logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        self.logger.info("Recording activity in the following guilds:")
        for id in self.config['guilds']:
            self.logger.info(f"* {id}")

        self.logger.info("Setting presence to invisible")
        self.change_presence(status=discord.Status.invisible)

        # All done setting up
        self.logger.info("")
        self.logger.info("Ready!")
        self.ready = True

    async def on_message(self, message):
        self.logger.debug(f"Message id {message.id} created")
        if not self._accept_message(message):
            return

        self._log(message, 'created')

        with self.sql.transaction():
            self.sql.add_message(message)

    async def on_message_edit(self, before, after):
        self.logger.debug(f"Message id {after.id} edited")
        if not self._accept_message(after):
            return

        self._log(after, 'edited')

        with self.sql.transaction():
            self.sql.edit_message(before, after)

    async def on_message_delete(self, message):
        self.logger.debug(f"Message id {message.id} deleted")
        if not self._accept_message(message):
            return

        self._log(message, 'deleted')

        with self.sql.transaction():
            self.sql.remove_message(message)

    async def on_typing(self, channel, user, when):
        self.logger.debug(f"User id {user.id} is typing")
        if not self._accept_channel(channel):
            return

        self._log_typing(channel, user)

        with self.sql.transaction():
            self.sql.typing(channel, user, when)

    async def on_reaction_add(self, reaction, user):
        self.logger.debug(f"Reaction {reaction.emoji} added")
        if not self._accept_message(reaction.message):
            return

        self._log_react(reaction, user, 'reacted with')

        self.logger.warn("TODO: handling for on_reaction_add")
        #with self.sql.transaction():
            #self.sql.add_reaction(reaction, user)

    async def on_reaction_remove(self, reaction, user):
        self.logger.debug(f"Reaction {reaction.emoji} removed")
        if not self._accept_message(reaction.message):
            return

        self._log_react(reaction, user, 'removed a reaction of ')

        self.logger.warn("TODO: handling for on_reaction_remove")
        #with self.sql.transaction():
            #self.sql.remove_reaction(reaction, user)

    async def on_reaction_clear(self, message, reactions):
        self.logger.debug(f"Reactions from {message.id} cleared")
        if not self._accept_message(message):
            return

        self.logger.info(f"All reactions on message id {message.id} cleared")

        self.logger.warn("TODO: handling for on_reaction_clear")
        #with self.sql.transaction():
            #self.sql.clear_reactions(message)

    async def on_guild_channel_create(self, channel):
        self.logger.debug(f"Channel was created in guild {channel.guild.id}")
        if not self._accept_channel(channel):
            return

        self.logger.info(f"Channel #{channel.name} created in {channel.guild.name}")

        with self.sql.transaction():
            self.sql.add_channel(channel)

    async def on_guild_channel_delete(self, channel):
        self.logger.debug(f"Channel was deleted in guild {channel.guild.id}")
        if not self._accept_channel(channel):
            return

        self.logger.info(f"Channel #{channel.name} deleted in {channel.guild.name}")

        with self.sql.transaction():
            self.sql.remove_channel(channel)

    async def on_guild_channel_update(self, before, after):
        self.logger.debug(f"Channel was updated in guild {after.guild.id}")
        if not self._accept_channel(after):
            return

        if before.name != after.name:
            changed = f' (now {after.name})'
        else:
            changed = ''
        self.logger.info(f"Channel #{before.name}{changed} was changed in {after.guild.name}")

        with self.sql.transaction():
            self.sql.update_channel(before, after)

    async def on_guild_channel_pins_update(self, channel, last_pin):
        self.logger.debug(f"Channel {channel.id} got a pin update")
        if not self._accept_channel(channel):
            return

        self.logger.info(f"Channel #{channel.name} got a pin update")
        self.logger.warn("TODO: handling for on_guild_channel_pins_update")

    async def on_member_join(self, member):
        self.logger.debug(f"Member {member.id} joined guild {member.guild.id}")
        if not self._accept_guild(member.guild):
            return

        self.logger.info(f"Member {member.name} has joined {member.guild.name}")

        with self.sql.transaction():
            self.sql.add_user(member)

    async def on_member_remove(self, member):
        self.logger.debug(f"Member {member.id} left guild {member.guild.id}")
        if not self._accept_guild(member.guild):
            return

        self.logger.info(f"Member {member.name} has left {member.guild.name}")

        with self.sql.transaction():
            self.sql.remove_user(member)

    async def on_member_update(self, before, after):
        self.logger.debug(f"Member {after.id} was updated in guild {after.guild.id}")
        if not self._accept_guild(after.guild):
            return

        # Certain changes that we don't care about can trigger this event
        before.status = after.status
        before.game = after.game
        if before == after:
            self.logger.debug("It was only a status change")
            return

        if before.name != after.name:
            changed = f' (now {after.name})'
        else:
            changed = ''
        self.logger.info(f"Member {before.name}{changed} was changed in {after.guild.name}")

        with self.sql.transaction():
            self.sql.update_user(after)

    async def on_guild_role_create(self, role):
        self.logger.debug(f"Role {role.id} was created in guild {role.guild.id}")
        if not self._accept_guild(role.guild):
            return

        self.logger.info(f"Role {role.name} was created in {role.guild.name}")

        with self.sql.transaction():
            self.sql.add_role(role)

    async def on_guild_role_delete(self, role):
        self.logger.debug(f"Role {role.id} was created in guild {role.guild.id}")
        if not self._accept_guild(role.guild):
            return

        self.logger.info(f"Role {role.name} was deleted in {role.guild.name}")

        with self.sql.transaction():
            self.sql.remove_role(role)

    async def on_guild_role_update(self, before, after):
        self.logger.debug(f"Role {after.id} was created in guild {after.guild.id}")
        if not self._accept_guild(after.guild):
            return

        if before.name != after.name:
            changed = f' (now {after.name})'
        else:
            changed = ''
        self.logger.info(f"Role {before.name}{changed} was changed in {after.guild.name}")

        with self.sql.transaction():
            self.sql.update_role(after)

    async def on_guild_emojis_update(self, guild, before, after):
        before = set(before)
        after = set(before)

        with self.sql.transaction():
            for emoji in after - before:
                self.sql.add_emoji(emoji)
            for emoji in before - after:
                self.sql.remove_emoji(emoji)

