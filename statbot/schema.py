import discord
from sqlalchemy import (
    ARRAY,
    Boolean,
    BigInteger,
    Column,
    DateTime,
    Enum,
    Integer,
    JSON,
    LargeBinary,
    SmallInteger,
    String,
    Table,
    Unicode,
    UnicodeText,
    ForeignKey,
    MetaData,
    UniqueConstraint,
)

from .mention import MentionType

class DiscordMetadata:
    def __init__(self, db):
        self.metadata_obj = MetaData(db)

        self.tb_messages = Table(
            "messages",
            self.metadata_obj,
            Column("message_id", BigInteger, primary_key=True),
            Column("created_at", DateTime),
            Column("edited_at", DateTime, nullable=True),
            Column("deleted_at", DateTime, nullable=True),
            Column("message_type", Enum(discord.MessageType)),
            Column("system_content", UnicodeText),
            Column("content", UnicodeText),
            Column("embeds", JSON),
            Column("attachments", SmallInteger),
            Column("webhook_id", BigInteger, nullable=True),
            Column("int_user_id", BigInteger),
            Column("channel_id", BigInteger, ForeignKey("channels.channel_id")),
            Column("guild_id", BigInteger, ForeignKey("guilds.guild_id")),
        )

        self.tb_reactions = Table(
            "reactions",
            self.metadata_obj,
            Column("message_id", BigInteger),
            Column("emoji_id", BigInteger),
            Column("emoji_unicode", Unicode(7)),
            Column("int_user_id", BigInteger, ForeignKey("users.int_user_id")),
            Column("created_at", DateTime, nullable=True),
            Column("deleted_at", DateTime, nullable=True),
            Column("channel_id", BigInteger, ForeignKey("channels.channel_id")),
            Column("guild_id", BigInteger, ForeignKey("guilds.guild_id")),
            UniqueConstraint(
                "message_id",
                "emoji_id",
                "emoji_unicode",
                "int_user_id",
                "created_at",
                name="uq_reactions",
            ),
        )

        self.tb_typing = Table(
            "typing",
            self.metadata_obj,
            Column("timestamp", DateTime),
            Column("int_user_id", BigInteger, ForeignKey("users.int_user_id")),
            Column("channel_id", BigInteger, ForeignKey("channels.channel_id")),
            Column("guild_id", BigInteger, ForeignKey("guilds.guild_id")),
            UniqueConstraint(
                "timestamp", "int_user_id", "channel_id", "guild_id", name="uq_typing"
            ),
        )

        self.tb_pins = Table(
            "pins",
            self.metadata_obj,
            Column("pin_id", BigInteger, primary_key=True),
            Column(
                "message_id",
                BigInteger,
                ForeignKey("messages.message_id"),
                primary_key=True,
            ),
            Column("pinner_id", BigInteger, ForeignKey("users.int_user_id")),
            Column("int_user_id", BigInteger, ForeignKey("users.int_user_id")),
            Column("channel_id", BigInteger, ForeignKey("channels.channel_id")),
            Column("guild_id", BigInteger, ForeignKey("guilds.guild_id")),
        )

        self.tb_mentions = Table(
            "mentions",
            self.metadata_obj,
            Column("mentioned_id", BigInteger, primary_key=True),
            Column("type", Enum(MentionType), primary_key=True),
            Column(
                "message_id",
                BigInteger,
                ForeignKey("messages.message_id"),
                primary_key=True,
            ),
            Column("channel_id", BigInteger, ForeignKey("channels.channel_id")),
            Column("guild_id", BigInteger, ForeignKey("guilds.guild_id")),
            UniqueConstraint("mentioned_id", "type", "message_id", name="uq_mention"),
        )

        self.tb_guilds = Table(
            "guilds",
            self.metadata_obj,
            Column("guild_id", BigInteger, primary_key=True),
            Column("int_owner_id", BigInteger, ForeignKey("users.int_user_id")),
            Column("name", Unicode),
            Column("icon", String),
            Column("voice_region", Enum(discord.VoiceRegion)),
            Column("afk_channel_id", BigInteger, nullable=True),
            Column("afk_timeout", Integer),
            Column("mfa", Boolean),
            Column("verification_level", Enum(discord.VerificationLevel)),
            Column("explicit_content_filter", Enum(discord.ContentFilter)),
            Column("features", ARRAY(String)),
            Column("splash", String, nullable=True),
        )

        self.tb_channels = Table(
            "channels",
            self.metadata_obj,
            Column("channel_id", BigInteger, primary_key=True),
            Column("name", String),
            Column("is_nsfw", Boolean),
            Column("is_deleted", Boolean),
            Column("position", SmallInteger),
            Column("topic", UnicodeText, nullable=True),
            Column("changed_roles", ARRAY(BigInteger)),
            Column(
                "category_id",
                BigInteger,
                ForeignKey("channel_categories.category_id"),
                nullable=True,
            ),
            Column("guild_id", BigInteger, ForeignKey("guilds.guild_id")),
        )

        self.tb_voice_channels = Table(
            "voice_channels",
            self.metadata_obj,
            Column("voice_channel_id", BigInteger, primary_key=True),
            Column("name", Unicode),
            Column("is_deleted", Boolean),
            Column("position", SmallInteger),
            Column("bitrate", Integer),
            Column("user_limit", SmallInteger),
            Column("changed_roles", ARRAY(BigInteger)),
            Column(
                "category_id",
                BigInteger,
                ForeignKey("channel_categories.category_id"),
                nullable=True,
            ),
            Column("guild_id", BigInteger, ForeignKey("guilds.guild_id")),
        )

        self.tb_channel_categories = Table(
            "channel_categories",
            self.metadata_obj,
            Column("category_id", BigInteger, primary_key=True),
            Column("name", Unicode),
            Column("position", SmallInteger),
            Column("is_deleted", Boolean),
            Column("is_nsfw", Boolean),
            Column("changed_roles", ARRAY(BigInteger)),
            Column(
                "parent_category_id",
                BigInteger,
                ForeignKey("channel_categories.category_id"),
                nullable=True,
            ),
            Column("guild_id", BigInteger, ForeignKey("guilds.guild_id")),
        )

        self.tb_users = Table(
            "users",
            self.metadata_obj,
            Column("int_user_id", BigInteger, primary_key=True),
            Column("real_user_id", BigInteger),
            Column("name", Unicode),
            Column("discriminator", SmallInteger),
            Column("avatar", String, nullable=True),
            Column("is_deleted", Boolean),
            Column("is_bot", Boolean),
        )

        self.tb_guild_membership = Table(
            "guild_membership",
            self.metadata_obj,
            Column(
                "int_user_id",
                BigInteger,
                ForeignKey("users.int_user_id"),
                primary_key=True,
            ),
            Column("guild_id", BigInteger, ForeignKey("guilds.guild_id"), primary_key=True),
            Column("is_member", Boolean),
            Column("joined_at", DateTime, nullable=True),
            Column("nick", Unicode(32), nullable=True),
            UniqueConstraint("int_user_id", "guild_id", name="uq_guild_membership"),
        )

        self.tb_role_membership = Table(
            "role_membership",
            self.metadata_obj,
            Column("role_id", BigInteger, ForeignKey("roles.role_id")),
            Column("guild_id", BigInteger, ForeignKey("guilds.guild_id")),
            Column("int_user_id", BigInteger, ForeignKey("users.int_user_id")),
            UniqueConstraint("role_id", "int_user_id", name="uq_role_membership"),
        )

        self.tb_avatar_history = Table(
            "avatar_history",
            self.metadata_obj,
            Column("user_id", BigInteger, primary_key=True),
            Column("timestamp", DateTime, primary_key=True),
            Column("avatar", LargeBinary),
            Column("avatar_ext", String),
        )

        self.tb_username_history = Table(
            "username_history",
            self.metadata_obj,
            Column("user_id", BigInteger, primary_key=True),
            Column("timestamp", DateTime, primary_key=True),
            Column("username", Unicode),
        )

        self.tb_nickname_history = Table(
            "nickname_history",
            self.metadata_obj,
            Column("user_id", BigInteger, primary_key=True),
            Column("timestamp", DateTime, primary_key=True),
            Column("nickname", Unicode),
        )

        self.tb_emojis = Table(
            "emojis",
            self.metadata_obj,
            Column("emoji_id", BigInteger),
            Column("emoji_unicode", Unicode(7)),
            Column("is_custom", Boolean),
            Column("is_managed", Boolean, nullable=True),
            Column("is_deleted", Boolean),
            Column("name", ARRAY(String)),
            Column("category", ARRAY(String)),
            Column("roles", ARRAY(BigInteger), nullable=True),
            Column("guild_id", BigInteger, nullable=True),
            UniqueConstraint("emoji_id", "emoji_unicode", name="uq_emoji"),
        )

        self.tb_roles = Table(
            "roles",
            self.metadata_obj,
            Column("role_id", BigInteger, primary_key=True),
            Column("name", Unicode),
            Column("color", Integer),
            Column("raw_permissions", BigInteger),
            Column("guild_id", BigInteger, ForeignKey("guilds.guild_id")),
            Column("is_hoisted", Boolean),
            Column("is_managed", Boolean),
            Column("is_mentionable", Boolean),
            Column("is_deleted", Boolean),
            Column("position", SmallInteger),
        )

        self.tb_audit_log = Table(
            "audit_log",
            self.metadata_obj,
            Column("audit_entry_id", BigInteger, primary_key=True),
            Column("guild_id", BigInteger, ForeignKey("guilds.guild_id")),
            Column("action", Enum(discord.AuditLogAction)),
            Column("int_user_id", BigInteger, ForeignKey("users.int_user_id")),
            Column("reason", Unicode, nullable=True),
            Column("category", Enum(discord.AuditLogActionCategory), nullable=True),
            Column("before", JSON),
            Column("after", JSON),
            UniqueConstraint("audit_entry_id", "guild_id", name="uq_audit_log"),
        )

        self.tb_channel_crawl = Table(
            "channel_crawl",
            self.metadata_obj,
            Column(
                "channel_id",
                BigInteger,
                ForeignKey("channels.channel_id"),
                primary_key=True,
            ),
            Column("last_message_id", BigInteger),
        )

        self.tb_audit_log_crawl = Table(
            "audit_log_crawl",
            self.metadata_obj,
            Column("guild_id", BigInteger, ForeignKey("guilds.guild_id"), primary_key=True),
            Column("last_audit_entry_id", BigInteger),
        )
