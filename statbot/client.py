#
# client.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017-2018 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import re
import sys

from datetime import datetime
from io import BytesIO
import asyncio
import discord

from .emoji import EmojiData
from .util import null_logger

__all__ = [
    "EventIngestionClient",
]

EXTENSION_REGEX = re.compile(r"/\w+\.(\w+)(?:\?.+)?$")


def user_needs_update(before, after):
    """
    See if the given user update is something
    we care about.

    Returns 'False' for no difference or
    change we will ignore.
    """

    for attr in ("name", "discriminator", "avatar"):
        if getattr(before, attr) != getattr(after, attr):
            return True
    return False


def member_needs_update(before, after):
    """
    See if the given member update is something
    we care about.

    Returns 'False' for no difference or
    change we will ignore.
    """

    for attr in ("nick", "avatar", "roles"):
        if getattr(before, attr) != getattr(after, attr):
            return True
    return False


class EventIngestionClient(discord.Client):
    __slots__ = (
        "config",
        "logger",
        "sql",
        "crawlers",
        "crawler_logger",
        "ready",
        "sql_init",
        "hooks",
    )

    def __init__(
        self, config, sql, logger=null_logger, crawlers=None, crawler_logger=null_logger
    ):
        super().__init__(intents=discord.Intents.all())
        self.config = config
        self.logger = logger
        self.sql = sql
        self.crawlers = crawlers
        self.crawler_logger = crawler_logger
        self.sql_init = False
        self.hooks = {
            "on_guild_channel_create": None,
            "on_guild_channel_delete": None,
            "on_guild_channel_update": None,
            "on_thread_create": None,
            "on_thread_delete": None,
            "on_thread_update": None,
        }

    def run_with_token(self):
        return self.run(self.config["bot"]["token"])

    # Async initialization hook. See
    # https://gist.github.com/Rapptz/6706e1c8f23ac27c98cee4dd985c8120
    async def setup_hook(self):
        self.ready = asyncio.Event(loop=self.loop)

        if self.crawlers is None:
            return

        for Crawler in self.crawlers:
            crawler = Crawler(self, self.sql, self.config, self.crawler_logger)
            crawler.start()

    async def wait_until_ready(self):
        # Override wait method to wait until SQL data is also ready
        # At least as long as "await super().wait_until_ready()"
        await self.ready.wait()

    async def _accept_message(self, message):
        await self.wait_until_ready()

        if not hasattr(message, "guild"):
            self._log_ignored("Message not from a guild.")
            self._log_ignored("Ignoring message.")
            return False
        elif getattr(message.guild, "id", None) not in self.config["guild-ids"]:
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

        if not hasattr(channel, "guild"):
            self._log_ignored("Channel not in a guild.")
            self._log_ignored("Ignoring message.")
        elif getattr(channel.guild, "id", None) not in self.config["guild-ids"]:
            self._log_ignored("Event from a guild we don't care about.")
            self._log_ignored("Ignoring message.")
            return False
        else:
            return True

    async def _accept_guild(self, guild):
        await self.wait_until_ready()

        if getattr(guild, "id", None) not in self.config["guild-ids"]:
            self._log_ignored("Event from a guild we don't care about.")
            self._log_ignored("Ignoring message.")
            return False
        else:
            return True

    def _log(self, message, action):
        name = message.author.display_name
        guild = message.guild.name
        chan = message.channel.name

        self.logger.debug(f"Message {action} by {name} in {guild} #{chan}")
        if self.config["logger"]["full-messages"]:
            self.logger.info("<bom>")
            self.logger.info(message.content)
            self.logger.info("<eom>")

    def _log_typing(self, channel, user):
        name = user.display_name
        guild = channel.guild.name
        chan = channel.name

        self.logger.debug(f"Typing by {name} on {guild} #{chan}")

    def _log_react(self, reaction, user, action):
        name = user.display_name
        emote = EmojiData(reaction.emoji)
        count = reaction.count
        id = reaction.message.id

        self.logger.debug(f"{name} {action} {emote} (total {count}) on message id {id}")

    def _log_ignored(self, message):
        if self.config["logger"]["ignored-events"]:
            self.logger.debug(message)

    def _init_sql(self, txact):
        self.logger.info(f"Processing {len(self.users)} users...")
        for user in self.users:
            self.sql.upsert_user(txact, user)

        self.logger.info(f"Processing {len(self.guilds)} guilds...")
        allowed_guilds = [
            guild for guild in self.guilds if guild.id in set(self.config["guild-ids"])
        ]
        for guild in allowed_guilds:
            self.sql.upsert_guild(txact, guild)

            self.logger.info(f"Processing {len(guild.roles)} roles...")
            for role in guild.roles:
                self.sql.upsert_role(txact, role)

            self.logger.info(f"Processing {len(guild.emojis)} emojis...")
            for emoji in guild.emojis:
                self.sql.upsert_emoji(txact, emoji)

            self.logger.info(f"Processing {len(guild.members)} members...")
            for member in guild.members:
                self.sql.upsert_member(txact, member)

            # In case people left while the bot was down
            self.sql.remove_old_members(txact, guild)

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

            self.logger.info(f"Processing {len(categories)} channel categories...")
            for category in categories:
                self.sql.upsert_channel_category(txact, category)

            self.logger.info(f"Processing {len(text_channels)} channels...")
            for channel in text_channels:
                self.sql.upsert_channel(txact, channel)

            self.logger.info(f"Processing {len(voice_channels)} voice channels...")
            for channel in voice_channels:
                self.sql.upsert_voice_channel(txact, channel)

    async def on_ready(self):
        # Print welcome string
        self.logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        self.logger.info("Recording activity in the following guilds:")
        for id in self.config["guild-ids"]:
            guild = self.get_guild(id)
            if guild is not None:
                self.logger.info(f"* {guild.name} ({id})")
            else:
                self.logger.error(f"Unable to find guild ID {id}")
                sys.exit(1)

        if not self.sql_init:
            self.logger.info("Initializing SQL lookup tables...")
            with self.sql.transaction() as txact:
                self._init_sql(txact)
                self.sql_init = True

        # All done setting up
        self.logger.info("")
        self.logger.info("Ready!")
        self.ready.set()

    async def on_message(self, message):
        self._log_ignored(f"Message id {message.id} created")
        if not await self._accept_message(message):
            return

        self._log(message, "created")

        with self.sql.transaction() as txact:
            self.sql.add_message(txact, message)

    async def on_message_edit(self, before, after):
        self._log_ignored(f"Message id {after.id} edited")
        if not await self._accept_message(after):
            return

        self._log(after, "edited")

        with self.sql.transaction() as txact:
            self.sql.edit_message(txact, before, after)

    async def on_message_delete(self, message):
        self._log_ignored(f"Message id {message.id} deleted")
        if not await self._accept_message(message):
            return

        self._log(message, "deleted")

        with self.sql.transaction() as txact:
            self.sql.remove_message(txact, message)

    async def on_typing(self, channel, user, when):
        self._log_ignored(f"User id {user.id} is typing")
        if not await self._accept_channel(channel):
            return

        self._log_typing(channel, user)

        with self.sql.transaction() as txact:
            self.sql.typing(txact, channel, user, when)

    async def on_reaction_add(self, reaction, user):
        self._log_ignored(f"Reaction {reaction.emoji} added")
        if not await self._accept_message(reaction.message):
            return

        self._log_react(reaction, user, "reacted with")

        with self.sql.transaction() as txact:
            self.sql.add_reaction(txact, reaction, user)

    async def on_reaction_remove(self, reaction, user):
        self._log_ignored(f"Reaction {reaction.emoji} removed")
        if not await self._accept_message(reaction.message):
            return

        self._log_react(reaction, user, "removed a reaction of ")

        with self.sql.transaction() as txact:
            self.sql.remove_reaction(txact, reaction, user)

    async def on_reaction_clear(self, message, reactions):
        self._log_ignored(f"Reactions from {message.id} cleared")
        if not await self._accept_message(message):
            return

        self.logger.info(f"All reactions on message id {message.id} cleared")

        with self.sql.transaction() as txact:
            self.sql.clear_reactions(txact, message)

    async def on_guild_channel_create(self, channel):
        self._log_ignored(f"Channel was created in guild {channel.guild.id}")
        if not await self._accept_channel(channel):
            return

        if isinstance(channel, discord.VoiceChannel):
            self.logger.info(
                f"Voice channel {channel.name} created in {channel.guild.name}"
            )
            with self.sql.transaction() as txact:
                self.sql.add_voice_channel(txact, channel)
            return

        self.logger.info(f"Channel #{channel.name} created in {channel.guild.name}")
        with self.sql.transaction() as txact:
            self.sql.add_channel(txact, channel)

        # pylint: disable=not-callable
        hook = self.hooks["on_guild_channel_create"]
        if hook:
            self.logger.debug(f"Found hook {hook!r}, calling it")
            await hook(channel)

    async def on_guild_channel_delete(self, channel):
        self._log_ignored(f"Channel was deleted in guild {channel.guild.id}")
        if not await self._accept_channel(channel):
            return

        if isinstance(channel, discord.VoiceChannel):
            self.logger.info(
                f"Voice channel {channel.name} deleted in {channel.guild.name}"
            )
            with self.sql.transaction() as txact:
                self.sql.remove_voice_channel(txact, channel)
            return

        self.logger.info(f"Channel #{channel.name} deleted in {channel.guild.name}")
        with self.sql.transaction() as txact:
            self.sql.remove_channel(txact, channel)

        # pylint: disable=not-callable
        hook = self.hooks["on_guild_channel_delete"]
        if hook:
            self.logger.debug(f"Found hook {hook!r}, calling it")
            await hook(channel)

    async def on_guild_channel_update(self, before, after):
        self._log_ignored(f"Channel was updated in guild {after.guild.id}")
        if not await self._accept_channel(after):
            return

        if before.name != after.name:
            changed = f" (now {after.name})"
        else:
            changed = ""

        if isinstance(after, discord.TextChannel):
            self.logger.info(
                f"Channel #{before.name}{changed} was changed in {after.guild.name}"
            )

            with self.sql.transaction() as txact:
                self.sql.update_channel(txact, after)

            # pylint: disable=not-callable
            hook = self.hooks["on_guild_channel_update"]
            if hook:
                self.logger.debug(f"Found hook {hook!r}, calling it")
                await hook(before, after)
        elif isinstance(after, discord.VoiceChannel):
            self.logger.info(
                "Voice channel {before.name}{changed} was changed in {after.guild.name}"
            )

            with self.sql.transaction() as txact:
                self.sql.update_voice_channel(txact, after)
        elif isinstance(after, discord.CategoryChannel):
            self.logger.info(
                f"Channel category {before.name}{changed} was changed in {after.guild.name}"
            )

            with self.sql.transaction() as txact:
                self.sql.update_channel_category(txact, after)

    async def on_guild_channel_pins_update(self, channel, last_pin):
        self._log_ignored(f"Channel {channel.id} got a pin update")
        if not await self._accept_channel(channel):
            return

        self.logger.debug(f"Channel #{channel.name} got a pin update")
        self.logger.warn("TODO: handling for on_guild_channel_pins_update")

    async def on_member_join(self, member):
        self._log_ignored(f"Member {member.id} joined guild {member.guild.id}")
        if not await self._accept_guild(member.guild):
            return

        self.logger.debug(f"Member {member.name} has joined {member.guild.name}")

        with self.sql.transaction() as txact:
            self.sql.upsert_user(txact, member)
            self.sql.upsert_member(txact, member)

    async def on_member_remove(self, member):
        self._log_ignored(f"Member {member.id} left guild {member.guild.id}")
        if not await self._accept_guild(member.guild):
            return

        self.logger.debug(f"Member {member.name} has left {member.guild.name}")

        with self.sql.transaction() as txact:
            self.sql.remove_user(txact, member)
            self.sql.remove_member(txact, member)

    async def on_member_update(self, before, after):
        self._log_ignored(f"Member {after.id} was updated in guild {after.guild.id}")
        if not await self._accept_guild(after.guild):
            return

        if not member_needs_update(before, after):
            self._log_ignored("We don't care about this type of member update")
            return

        if before.display_name != after.display_name:
            changed = f" (now {after.name})"
        else:
            changed = ""
        self.logger.debug(
            f"Member {before.display_name}{changed} was changed in {after.guild.name}"
        )

        with self.sql.transaction() as txact:
            now = datetime.now()
            self.sql.update_member(txact, after)

            if before.nick != after.nick and after.nick is not None:
                self.sql.add_nickname(txact, before, now, after.nick)

    async def on_user_update(self, before, after):
        self._log_ignored(f"User {after.id} was updated")

        if not user_needs_update(before, after):
            self._log_ignored("We don't care about this kind user update")
            return

        if before.display_name != after.display_name:
            changed = f" (now {after.name})"
        else:
            changed = ""
        self.logger.debug(f"User {before.display_name}{changed} was changed")

        with self.sql.transaction() as txact:
            now = datetime.now()
            self.sql.update_user(txact, after)

            if before.avatar != after.avatar:
                avatar, avatar_ext = await self.get_avatar(after.avatar_url)
                self.sql.add_avatar(txact, before, now, avatar, avatar_ext)

            if before.name != after.name:
                self.sql.add_username(txact, before, now, after.name)

    async def get_avatar(self, asset):
        avatar = BytesIO()
        avatar_url = str(asset)
        await asset.save(avatar)

        match = EXTENSION_REGEX.findall(avatar_url)
        if not match:
            raise ValueError(f"Avatar URL does not match extension regex: {avatar_url}")

        avatar_ext = match[0]
        return avatar, avatar_ext

    async def on_guild_role_create(self, role):
        self._log_ignored(f"Role {role.id} was created in guild {role.guild.id}")
        if not await self._accept_guild(role.guild):
            return

        self.logger.info(f"Role {role.name} was created in {role.guild.name}")

        with self.sql.transaction() as txact:
            self.sql.add_role(txact, role)

    async def on_guild_role_delete(self, role):
        self._log_ignored(f"Role {role.id} was created in guild {role.guild.id}")
        if not await self._accept_guild(role.guild):
            return

        self.logger.info(f"Role {role.name} was deleted in {role.guild.name}")

        with self.sql.transaction() as txact:
            self.sql.remove_role(txact, role)

    async def on_guild_role_update(self, before, after):
        self._log_ignored(f"Role {after.id} was created in guild {after.guild.id}")
        if not await self._accept_guild(after.guild):
            return

        if before.name != after.name:
            changed = f" (now {after.name})"
        else:
            changed = ""
        self.logger.info(
            f"Role {before.name}{changed} was changed in {after.guild.name}"
        )

        with self.sql.transaction() as txact:
            self.sql.update_role(txact, after)

    async def on_guild_emojis_update(self, guild, before, after):
        before = set(before)
        after = set(before)

        with self.sql.transaction() as txact:
            for emoji in after - before:
                self.sql.add_emoji(txact, emoji)
            for emoji in before - after:
                self.sql.remove_emoji(txact, emoji)

    async def on_thread_create(self, thread: discord.Thread):
        self._log_ignored(f"Thread was created in guild {thread.guild.id}")
        if not await self._accept_channel(thread.parent):
            return

        self.logger.info(
            f"Thread {thread.name} created in guild {thread.guild.name}, channel {thread.parent.name}"
        )
        with self.sql.transaction() as txact:
            self.sql.add_thread(txact, thread)

        hook = self.hooks["on_thread_create"]
        if hook:
            self.logger.debug(f"Found hook {hook!r}, calling it")
            await hook(thread)

    async def on_thread_delete(self, thread: discord.Thread):
        self._log_ignored(f"Thread was deleted in guild {thread.guild.id}")
        if not await self._accept_channel(thread.parent):
            return

        self.logger.info(
            f"Thread {thread.name} deleted in guild {thread.guild.name}, channel {thread.parent.name}"
        )
        with self.sql.transaction() as txact:
            self.sql.remove_thread(txact, thread)

        hook = self.hooks["on_thread_delete"]
        if hook:
            self.logger.debug(f"Found hook {hook!r}, calling it")
            await hook(thread)

    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        self._log_ignored(f"Thread was updated in guild {after.guild.id}")
        if not await self._accept_channel(after.parent):
            return

        changed = f" (now {after.name})" if before.name != after.name else ""

        self.logger.info(
            (
                f"Thread {before.name}{changed} changed in guild {after.guild.name}, "
                f"channel {after.parent.name}"
            )
        )
        with self.sql.transaction() as txact:
            self.sql.update_thread(txact, after)

        hook = self.hooks["on_thread_update"]
        if hook:
            self.logger.debug(f"Found hook {hook!r}, calling it")
            await hook(before, after)

    async def on_thread_member_join(self, member: discord.ThreadMember):
        self._log_ignored(f"User id {member.id} joined thread {member.thread.name}")
        if not await self._accept_channel(member.thread.parent):
            return

        with self.sql.transaction() as txact:
            self.sql.add_thread_member(txact, member)

    async def on_thread_member_remove(self, member: discord.ThreadMember):
        self._log_ignored(f"User id {member.id} left thread {member.thread.name}")
        if not await self._accept_channel(member.thread.parent):
            return

        with self.sql.transaction() as txact:
            self.sql.remove_thread_member(txact, member)
