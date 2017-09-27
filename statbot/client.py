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

import asyncio
import discord

from .emoji import EmojiData
from .util import null_logger

__all__ = [
    'EventIngestionClient',
]

def member_needs_update(before, after):
    '''
    See if the given member update is something
    we care about.

    Returns 'False' for no difference or
    change we will ignore.
    '''

    for attr in ('name', 'discriminator', 'nick', 'avatar', 'roles'):
        if getattr(before, attr) != getattr(after, attr):
            return True
    return False

class EventIngestionClient(discord.Client):
    __slots__ = (
        'config',
        'logger',
        'sql',
        'ready',
        'hooks',
    )

    def __init__(self, config, sql, logger=null_logger):
        super().__init__()
        self.config = config
        self.logger = logger
        self.sql = sql
        self.ready = asyncio.Event()
        self.hooks = {
            'on_guild_channel_create': None,
            'on_guild_channel_delete': None,
            'on_guild_channel_update': None,
        }

    def run_with_token(self):
        return self.run(self.config['token'])

    async def wait_until_ready(self):
        # Override wait method to wait until SQL data is also ready
        # At least as long as "await super().wait_until_ready()"
        await self.ready.wait()

    async def _accept_message(self, message):
        await self.wait_until_ready()

        if not hasattr(message, 'guild'):
            self._log_ignored("Message not from a guild.")
            self._log_ignored("Ignoring message.")
            return False
        elif getattr(message.guild, 'id', None) not in self.config['guilds']:
            self._log_ignored("Message from a guild we don't care about.")
            self._log_ignored("Ignoring message.")
            return False
        elif message.type != discord.MessageType.default:
            self._log_ignored("Special type of message receieved.")
            self._log_ignored("Ignoring message.")
        else:
            return True

    async def _accept_channel(self, channel):
        await self.wait_until_ready()

        if not hasattr(channel, 'guild'):
            self._log_ignored("Channel not in a guild.")
            self._log_ignored("Ignoring message.")
        elif getattr(channel.guild, 'id', None) not in self.config['guilds']:
            self._log_ignored("Event from a guild we don't care about.")
            self._log_ignored("Ignoring message.")
            return False
        else:
            return True

    async def _accept_guild(self, guild):
        await self.wait_until_ready()

        if getattr(guild, 'id', None) not in self.config['guilds']:
            self._log_ignored("Event from a guild we don't care about.")
            self._log_ignored("Ignoring message.")
            return False
        else:
            return True

    def _log(self, message, action):
        name = message.author.display_name
        guild = message.guild.name
        chan = message.channel.name

        self.logger.info(f"Message {action} by {name} in {guild} #{chan}")
        if self.config['logger']['full-messages']:
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
        emote = EmojiData(reaction.emoji)
        count = reaction.count
        id = reaction.message.id

        self.logger.info(f"{name} {action} {emote} (total {count}) on message id {id}")

    def _log_ignored(self, message):
        if self.config['logger']['ignored-events']:
            self.logger.debug(message)

    def _init_sql(self, trans):
        self.logger.debug(f"Processing {len(self.users)} users...")
        for user in self.users:
            self.sql.upsert_user(trans, user)

        self.logger.debug(f"Processing {len(self.guilds)} guilds...")
        for guild in self.guilds:
            self.sql.upsert_guild(trans, guild)

            self.logger.debug(f"Processing {len(guild.roles)} roles...")
            for role in guild.roles:
                self.sql.upsert_role(trans, role)

            self.logger.debug(f"Processing {len(guild.emojis)} emojis...")
            for emoji in guild.emojis:
                self.sql.upsert_emoji(trans, emoji)

            self.logger.debug(f"Processing {len(guild.members)} members...")
            for member in guild.members:
                self.sql.upsert_member(trans, member)

            text_channels = []
            voice_channels = []
            categories = []
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    text_channels.append(channel)
                elif isinstance(channel, discord.VoiceChannel):
                    voice_channels.append(channel)
                elif isinstance(channel, discord.CategoryChannel):
                    categories.append(channel)

            self.logger.debug(f"Processing {len(categories)} channel categories...")
            for category in categories:
                self.sql.upsert_channel_category(trans, category)

            self.logger.debug(f"Processing {len(text_channels)} channels...")
            for channel in text_channels:
                self.sql.upsert_channel(trans, channel)

            self.logger.debug(f"Processing {len(voice_channels)} voice channels...")
            for channel in voice_channels:
                self.sql.upsert_voice_channel(trans, channel)

    async def on_ready(self):
        # Print welcome string
        self.logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        self.logger.info("Recording activity in the following guilds:")
        for id in self.config['guilds']:
            guild = self.get_guild(id)
            self.logger.info(f"* {guild.name} ({id})")

        self.logger.info("Setting presence to invisible")
        self.change_presence(status=discord.Status.invisible)

        self.logger.info("Initializing SQL lookup tables...")
        with self.sql.transaction() as trans:
            self._init_sql(trans)

        # All done setting up
        self.logger.info("")
        self.logger.info("Ready!")
        self.ready.set()

    async def on_message(self, message):
        self._log_ignored(f"Message id {message.id} created")
        if not await self._accept_message(message):
            return

        self._log(message, 'created')

        with self.sql.transaction() as trans:
            self.sql.add_message(trans, message)

    async def on_message_edit(self, before, after):
        self._log_ignored(f"Message id {after.id} edited")
        if not await self._accept_message(after):
            return

        self._log(after, 'edited')

        with self.sql.transaction() as trans:
            self.sql.edit_message(trans, before, after)

    async def on_message_delete(self, message):
        self._log_ignored(f"Message id {message.id} deleted")
        if not await self._accept_message(message):
            return

        self._log(message, 'deleted')

        with self.sql.transaction() as trans:
            self.sql.remove_message(trans, message)

    async def on_typing(self, channel, user, when):
        self._log_ignored(f"User id {user.id} is typing")
        if not await self._accept_channel(channel):
            return

        self._log_typing(channel, user)

        with self.sql.transaction() as trans:
            self.sql.typing(trans, channel, user, when)

    async def on_reaction_add(self, reaction, user):
        self._log_ignored(f"Reaction {reaction.emoji} added")
        if not await self._accept_message(reaction.message):
            return

        self._log_react(reaction, user, 'reacted with')

        with self.sql.transaction() as trans:
            self.sql.add_reaction(trans, reaction, user)

    async def on_reaction_remove(self, reaction, user):
        self._log_ignored(f"Reaction {reaction.emoji} removed")
        if not await self._accept_message(reaction.message):
            return

        self._log_react(reaction, user, 'removed a reaction of ')

        with self.sql.transaction() as trans:
            self.sql.remove_reaction(trans, reaction, user)

    async def on_reaction_clear(self, message, reactions):
        self._log_ignored(f"Reactions from {message.id} cleared")
        if not await self._accept_message(message):
            return

        self.logger.info(f"All reactions on message id {message.id} cleared")

        with self.sql.transaction() as trans:
            self.sql.clear_reactions(trans, message)

    async def on_guild_channel_create(self, channel):
        self._log_ignored(f"Channel was created in guild {channel.guild.id}")
        if not await self._accept_channel(channel):
            return

        if isinstance(channel, discord.VoiceChannel):
            self.logger.info(f"Voice channel {channel.name} deleted in {channel.guild.name}")
            with self.sql.transaction() as trans:
                self.sql.add_voice_channel(trans, channel)
            return

        self.logger.info(f"Channel #{channel.name} created in {channel.guild.name}")
        with self.sql.transaction() as trans:
            self.sql.add_channel(trans, channel)

        # pylint: disable=not-callable
        hook = self.hooks['on_guild_channel_create']
        if hook:
            self.logger.debug(f"Found hook {hook!r}, calling it")
            await hook(channel)

    async def on_guild_channel_delete(self, channel):
        self._log_ignored(f"Channel was deleted in guild {channel.guild.id}")
        if not await self._accept_channel(channel):
            return

        if isinstance(channel, discord.VoiceChannel):
            self.logger.info(f"Voice channel {channel.name} deleted in {channel.guild.name}")
            with self.sql.transaction() as trans:
                self.sql.remove_voice_channel(trans, channel)
            return

        self.logger.info(f"Channel #{channel.name} deleted in {channel.guild.name}")
        with self.sql.transaction() as trans:
            self.sql.remove_channel(trans, channel)

        # pylint: disable=not-callable
        hook = self.hooks['on_guild_channel_delete']
        if hook:
            self.logger.debug(f"Found hook {hook!r}, calling it")
            await hook(channel)

    async def on_guild_channel_update(self, before, after):
        self._log_ignored(f"Channel was updated in guild {after.guild.id}")
        if not await self._accept_channel(after):
            return

        if before.name != after.name:
            changed = f' (now {after.name})'
        else:
            changed = ''

        if isinstance(after, discord.TextChannel):
            self.logger.info(f"Channel #{before.name}{changed} was changed in {after.guild.name}")

            with self.sql.transaction() as trans:
                self.sql.update_channel(trans, after)

            # pylint: disable=not-callable
            hook = self.hooks['on_guild_channel_update']
            if hook:
                self.logger.debug(f"Found hook {hook!r}, calling it")
                await hook(before, after)
        elif isinstance(after, discord.VoiceChannel):
            self.logger.info("Voice channel {before.name}{changed} was changed in {after.guild.name}")

            with self.sql.transaction() as trans:
                self.sql.update_voice_channel(trans, after)
        elif isinstance(after, discord.CategoryChannel):
            self.logger.info(f"Channel category {before.name}{changed} was changed in {after.guild.name}")

            with self.sql.transaction() as trans:
                self.sql.update_channel_category(trans, after)

    async def on_guild_channel_pins_update(self, channel, last_pin):
        self._log_ignored(f"Channel {channel.id} got a pin update")
        if not await self._accept_channel(channel):
            return

        self.logger.info(f"Channel #{channel.name} got a pin update")
        self.logger.warn("TODO: handling for on_guild_channel_pins_update")

    async def on_member_join(self, member):
        self._log_ignored(f"Member {member.id} joined guild {member.guild.id}")
        if not await self._accept_guild(member.guild):
            return

        self.logger.info(f"Member {member.name} has joined {member.guild.name}")

        with self.sql.transaction() as trans:
            self.sql.upsert_user(trans, member)
            self.sql.add_member(trans, member)

    async def on_member_remove(self, member):
        self._log_ignored(f"Member {member.id} left guild {member.guild.id}")
        if not await self._accept_guild(member.guild):
            return

        self.logger.info(f"Member {member.name} has left {member.guild.name}")

        with self.sql.transaction() as trans:
            self.sql.remove_user(trans, member)
            self.sql.remove_member(trans, member)

    async def on_member_update(self, before, after):
        self._log_ignored(f"Member {after.id} was updated in guild {after.guild.id}")
        if not await self._accept_guild(after.guild):
            return

        if not member_needs_update(before, after):
            self._log_ignored("We don't care about this type of member update")
            return

        if before.display_name != after.display_name:
            changed = f' (now {after.name})'
        else:
            changed = ''
        self.logger.info(f"Member {before.display_name}{changed} was changed in {after.guild.name}")

        with self.sql.transaction() as trans:
            self.sql.update_user(trans, after)
            self.sql.update_member(trans, after)

    async def on_guild_role_create(self, role):
        self._log_ignored(f"Role {role.id} was created in guild {role.guild.id}")
        if not await self._accept_guild(role.guild):
            return

        self.logger.info(f"Role {role.name} was created in {role.guild.name}")

        with self.sql.transaction() as trans:
            self.sql.add_role(trans, role)

    async def on_guild_role_delete(self, role):
        self._log_ignored(f"Role {role.id} was created in guild {role.guild.id}")
        if not await self._accept_guild(role.guild):
            return

        self.logger.info(f"Role {role.name} was deleted in {role.guild.name}")

        with self.sql.transaction() as trans:
            self.sql.remove_role(trans, role)

    async def on_guild_role_update(self, before, after):
        self._log_ignored(f"Role {after.id} was created in guild {after.guild.id}")
        if not await self._accept_guild(after.guild):
            return

        if before.name != after.name:
            changed = f' (now {after.name})'
        else:
            changed = ''
        self.logger.info(f"Role {before.name}{changed} was changed in {after.guild.name}")

        with self.sql.transaction() as trans:
            self.sql.update_role(trans, after)

    async def on_guild_emojis_update(self, guild, before, after):
        before = set(before)
        after = set(before)

        with self.sql.transaction() as trans:
            for emoji in after - before:
                self.sql.add_emoji(trans, emoji)
            for emoji in before - after:
                self.sql.remove_emoji(trans, emoji)
