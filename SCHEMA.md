## Schemas by Table

### messages
| Column Name         | Type          | Other                       |
|---------------------|---------------|-----------------------------|
| `message_id`        | `BigInteger`  | Primary key                 |
| `created_at`        | `DateTime`    |                             |
| `edited_at`         | `DateTime`    | Nullable                    |
| `deleted_at`        | `DateTime`    | Nullable                    |
| `message_type`      | `Enum`        | `discord.MessageType`       |
| `system_content`    | `UnicodeText` |                             |
| `content`           | `UnicodeText` |                             |
| `embeds`            | `JSON`        |                             |
| `attachments`       | `SmallInteger`|                             |
| `webhook_id`        | `BigInteger`  |                             |
| `user_id`           | `BigInteger`  |                             |
| `channel_id`        | `BigInteger`  |                             |
| `guild_id`          | `BigInteger`  |                             |

This table is the real heart of Statbot. It stores every single message in all Discord guilds that the bot is in. The fields you most likely care about are `message_id`, that message's globally unique identifier, `content`, what the message contains, and `user_id`, `channel_id`, and `guild_id`, where this message was sent and who sent it.

These records are only ever appended or updated, not deleted. Messages that have been altered (edited or deleted) are tracked as such by setting those corresponding columns to timestamps telling when the action occurred.

For information on [`message_type`](https://discordpy.readthedocs.io/en/rewrite/api.html#discord.Message.system_content) or [`system_content`](https://discordpy.readthedocs.io/en/rewrite/api.html#discord.Message.type), see the [discord.py API documentation](https://discordpy.readthedocs.io/en/rewrite/api.html).

The `embeds` column is a JSON field containing a list of the embeds stored with this messages. This includes both manual embeds (the kind bots send) and automatic embeds (the kind that appear when you post links). For a typical message this will be `{}`. For more information on what fields it may contain, see [`discord.Embed`](https://discordpy.readthedocs.io/en/rewrite/api.html#embed).

The `attachments` column only stores how many attachments were added to this message.
The actual links to those files are automatically appended to the message's `content`s.

### reactions
| Column Name         | Type          | Other                       |
|---------------------|---------------|-----------------------------|
| `message_id`        | `BigInteger`  |                             |
| `emoji_id`          | `BigInteger`  |                             |
| `emoji_unicode`     | `Unicode(7)`  |                             |
| `user_id`           | `BigInteger`  |                             |
| `created_at`        | `BigInteger`  | Nullable                    |
| `deleted_at`        | `BigInteger`  | Nullable                    |
| `channel_id`        | `BigInteger`  |                             |
| `guild_id`          | `BigInteger`  |                             |

Unique constraint `uq_reactions`: `message_id`, `emoji_id`, `emoji_unicode`, `user_id`, `created_at`.

This table stores reactions on messages. There is no primary key for this table since you can have duplicate reactions on the same message with the same emote by the same person. However, they are nearly always going to happen at different times, making the unique constraint useful. In cases where this is not the case, the reaction will not be tracked.

Live reactions have more data than crawled ones. Crawled reactions that are later deleted cannot be seen by Statbot (since they're deleted), and those it does find do not have a corresponding creation timestamp. In either of these cases, the row will either not exist or will have `NULL` for the corresponding column.

For an explanation of `emoji_id` / `emoji_unicode`, see the "Emoji Data".

### typing
| Column Name         | Type          | Other                       |
|---------------------|---------------|-----------------------------|
| `timestamp`         | `DateTime`    |                             |
| `user_id`           | `BigInteger`  |                             |
| `channel_id`        | `BigInteger`  |                             |
| `guild_id`          | `BigInteger`  |                             |

Unique constraint `uq_typing`: `timestamp`, `user_id`, `channel_id`, `guild_id`.

This table tracks the "... is typing" events received by the client. Since they are live, the crawler cannot capture any events of this type. They do not have IDs, so instead the timestamp is sampled from the bot, and then inserted with the other data.

If you are trying to recreate a channel's activity, note that typing events are intended to last 10 seconds or until that user sends a message in that channel, whichever is earliest.

### pins
| Column Name         | Type          | Other                       |
|---------------------|---------------|-----------------------------|
| `pin_id`            | `BigInteger`  | Primary key                 |
| `message_id`        | `BigInteger`  |                             |
| `pinner_id`         | `BigInteger`  |                             |
| `user_id`           | `BigInteger`  |                             |
| `channel_id`        | `BigInteger`  |                             |
| `guild_id`          | `BigInteger`  |                             |

**This is likely what the table will look like when this feature is ready. Anything can change in the mean time.**

This schema is similar to the `messages` schema, but there are some important details to clarify. Every time you have a pin, there are two users involved: the pinner and the author. These may or may not be the same person. Likewise, you have two IDs: the pin message ID, and the message ID of the item being pinned.

Whenever you pin something, it creates a system message, that "[user] pinned a message to this channel." This message's "author" is the person who did the pinning. This message's ID is the `pin_id`, and is what is used to track pin ownership (i.e. who pinned which message).

### mentions
| Column Name         | Type          | Other                       |
|---------------------|---------------|-----------------------------|
| `mentioned_id`      | `BigInteger`  | Primary key                 |
| `type`              | `Enum`        | Primary key                 |
| `message_id`        | `BigInteger`  | Primary key                 |
| `channel_id`        | `BigInteger`  |                             |
| `guild_id`          | `BigInteger`  |                             |

Unique constraint `uq_mention`: `mentioned_id`, `type`, `message_id`

This table tracks mentions. There are three kinds that are noted, which correspond to the possible values of the `type` column: `USER`, `ROLE`, and `CHANNEL`.

The `mentioned_id` column is the actual thing being mentioned. So if the `type` is `USER`, then this value is likely a user's ID. However, **this value can be invalid!** If users manually construct mentions, or they mention somebody not known to Statbot, these IDs may not correspond to anything.

A separate row is produced for each mention in a message. Duplicates in a message are ignored, as you can see from the unique constraint.

Note that `@everyone` and `@here` are special. They are not currently tracked by this table. If you wish to search for them, query `messages` based on the literal strings `@everyone` or `@here`.

### guilds
| Column Name               | Type            | Other                       |
|---------------------------|-----------------|-----------------------------|
| `guild_id`                | `BigInteger`    | Primary key                 |
| `owner_id`                | `BigInteger`    |                             |
| `name`                    | `Unicode`       |                             |
| `icon`                    | `String`        |                             |
| `voice_region`            | `Enum`          | `discord.VoiceRegion`       |
| `afk_channel_id`          | `BigInteger`    | Nullable                    |
| `afk_timeout`             | `Integer`       |                             |
| `mfa`                     | `Boolean`       |                             |
| `verification_level`      | `Enum`          | `discord.VerificationLevel` |
| `explicit_content_filter` | `Enum`          | `discord.ContentFilter`     |
| `features`                | `Array[String]` |                             |
| `splash`                  | `String`        | Nullable                    |

This table provides look-up information about known guilds. The columns in this schema more or less correspond to the [`discord.Guild` object](https://discordpy.readthedocs.io/en/rewrite/api.html#guild). The biggest change is `mfa` is a boolean instead of an integer, reflecting whether it's enabled or not.

### channels
| Column Name         | Type                | Other                       |
|---------------------|---------------------|-----------------------------|
| `channel_id`        | `BigInteger`        | Primary key                 |
| `name`              | `String`            |                             |
| `is_nsfw`           | `Boolean`           |                             |
| `is_deleted`        | `Boolean`           |                             |
| `position`          | `SmallInteger`      |                             |
| `topic`             | `UnicodeText`       | Nullable                    |
| `changed_roles`     | `Array[BigInteger]` |                             |
| `category_id`       | `BigInteger`        | Nullable                    |
| `guild_id`          | `BigInteger`        |                             |

This table provides look-up information about text channels. The columns in this schema more or less correspond to the [`discord.TextChannel` object](https://discordpy.readthedocs.io/en/rewrite/api.html#textchannel).

Channels that are deleted while the bot is running are marked as such, with all meta information in the last state the channel was observed in.

### voice\_channels
| Column Name         | Type                | Other                       |
|---------------------|---------------------|-----------------------------|
| `voice_channel_id`  | `BigInteger`        | Primary key                 |
| `name`              | `String`            |                             |
| `is_deleted`        | `Boolean`           |                             |
| `position`          | `SmallInteger`      |                             |
| `bitrate`           | `Integer`           |                             |
| `user_limit`        | `SmallInteger`      |                             |
| `changed_roles`     | `Array[BigInteger]` |                             |
| `category_id`       | `BigInteger`        | Nullable                    |
| `guild_id`          | `BigInteger`        |                             |

This table provides look-up information about voice channels. The columns in this schema more or less correspond to the [`discord.VoiceChannel` object](https://discordpy.readthedocs.io/en/rewrite/api.html#voicechannel).

Like with text channels, voice channels that are deleted are tracked as such.

### channel\_categories
| Column Name         | Type                | Other                       |
|---------------------|---------------------|-----------------------------|
| `category_id`       | `BigInteger`        | Primary key                 |
| `name`              | `Unicode`           |                             |
| `position`          | `SmallInteger`      |                             |
| `is_nsfw`           | `Boolean`           |                             |
| `is_deleted`        | `Boolean`           |                             |
| `changed_roles`     | `Array[BigInteger]` |                             |
| `parent_category_id`| `BigInteger`        | Nullable                    |
| `guild_id`          | `BigInteger`        |                             |

This table provides look-up information about channel categories. The columns in this schema more or less correspond to the [`discord.CategoryChannel` object](https://discordpy.readthedocs.io/en/rewrite/api.html#categorychannel).

Like with text channels, channel categories that are deleted are tracked as such.

### users
| Column Name         | Type          | Other                       |
|---------------------|---------------|-----------------------------|
| `user_id`           | `BigInteger`  | Primary key                 |
| `name`              | `Unicode`     |                             |
| `discriminator`     | `SmallInteger`|                             |
| `avatar`            | `String`      | Nullable                    |
| `is_deleted`        | `Boolean`     |                             |
| `is_bot`            | `Boolean`     |                             |

This table provides look-up information about all known users. The columns in this schema more or less correspond to the [`discord.User` object](https://discordpy.readthedocs.io/en/rewrite/api.html#user).

Like with text channels, users that delete their accounts are tracked as such.

If you want to query a user's nicknames, see the `guild_membership` table.

### roles
| Column Name         | Type          | Other                       |
|---------------------|---------------|-----------------------------|
| `role_id`           | `BigInteger`  |                             |
| `name`              | `Unicode`     |                             |
| `color`             | `Integer`     |                             |
| `raw_permissions`   | `BigInteger`  |                             |
| `guild_id`          | `BigInteger`  |                             |
| `is_hoisted`        | `Boolean`     |                             |
| `is_managed`        | `Boolean`     |                             |
| `is_mentionable`    | `Boolean`     |                             |
| `is_deleted`        | `Boolean`     |                             |
| `position`          | `SmallInteger`|                             |

This table provides look-up information about roles. The columns in this schema more or less correspond to the [`discord.Role` object](https://discordpy.readthedocs.io/en/rewrite/api.html#role).

Like with text channels, roles that are deleted are tracked as such.

### guild\_membership
| Column Name         | Type          | Other                       |
|---------------------|---------------|-----------------------------|
| `user_id`           | `BigInteger`  | Primary key                 |
| `guild_id`          | `BigInteger`  | Primary key                 |
| `is_member`         | `Boolean`     |                             |
| `joined_at`         | `DateTime`    | Nullable                    |
| `nick`              | `Unicode(32)` | Nullable                    |

Unique constraint `uq_guild_membership`: `user_id`, `guild_id`.

This table tracks which users are currently members in which guilds. If a user is currently a member of a guild, then the `is_member` column will be `true` and the `joined_at` column will be non-`NULL`. Note that it is possible for `is_member` to be `false` but have the `joined_at` column not be `NULL`. This is likely because the user joined the guild but then left.

This table also tracks user's nicknames per guild. If the `nick` column is
`NULL`, they have no nickname, and their display name is just their username.

### role\_membership
| Column Name         | Type          | Other                       |
|---------------------|---------------|-----------------------------|
| `role_id`           | `BigInteger`  |                             |
| `guild_id`          | `BigInteger`  |                             |
| `user_id`           | `BigInteger`  |                             |

Unique constraint `uq_role_membership`: `role_id`, `user_id`.

This table tracks which users have which roles. At the very least, this includes the `@everyone` role of that guild, which you can see from the presence of a row with a `role_id` and `guild_id` that have the same value.

Note that this is _not_ a way to check for membership. When a member leaves
a guild, all the rows in this table are preserved until they decide to rejoin
(and their roles are reassigned). If you want to see if a user is aa member of
a guild, use the `guild_membership` table.

### emojis
| Column Name         | Type                | Other                       |
|---------------------|---------------------|-----------------------------|
| `emoji_id`          | `BigInteger`        |                             |
| `emoji_unicode`     | `Unicode(7)`        |                             |
| `is_custom`         | `Boolean`           |                             |
| `is_managed`        | `Boolean`           | Nullable                    |
| `is_deleted`        | `Boolean`           |                             |
| `name`              | `Array[String]`     |                             |
| `category`          | `Array[String]`     |                             |
| `roles`             | `Array[BigInteger]` |                             |
| `guild_id`          | `BigInteger`        |                             |

Unique constraint `uq_emoji`: `emoji_id` and `emoji_unicode`.

For an explanation of `emoji_id` / `emoji_unicode`, see the "Emoji Data".

If the emoji is custom, then:
* the `is_custom` column will be set to `true`
* the `name` column will be an array of one, holding its assigned name
* the `category` column will be an array of one, with the string `custom`
* the `roles` column will be a list of which role IDs are permitted to use this emoji
* if the above array is empty it means that there are no restrictions imposed
* the `guild_id` column will have ID of the guild this emoji belongs to

If the emoji is unicode, then:
* the `is_custom` column will be set to `false`
* the `is_managed` and `is_deleted` columns will be set to `false`
* the `name` column will be an array of each unicode character's name in the string
* the `category` column will be an array of each unicode character's category in the string
* the `roles` column will be an empty array
* the `guild_id` column will be null

### audit\_log
| Column Name         | Type                | Other                                      |
|---------------------|---------------------|--------------------------------------------|
| `audit_entry_id`    | `BigInteger`        | Primary key                                |
| `guild_id`          | `BigInteger`        |                                            |
| `action`            | `Enum`              | `discord.AuditLogAction`                   |
| `user_id`           | `BigInteger`        |                                            |
| `reason`            | `Unicode`           | Nullable                                   |
| `category`          | `Enum`              | `discord.AuditLogActionCategory`, nullable |
| `before`            | `JSON`              |                                            |
| `after`             | `JSON`              |                                            |

Unique constraint `uq_audit_log`: `audit_entry_id` and `guild_id`.

This table records a particular entry in the audit log. It stores the entry ID and the associated guild, as well as which action was being performed. The `user_id` column refers to who was _performing_ the action, not the recipeient. `category` is a general type dictating whether this was some kind of creation, deletion, or update. It can also be `NULL`.

The `before` and `after` columns contain the change storted by this log entry. These JSON objects should have the same set of keys, and may contain `null` values. For instance, a record of a person removing their nickname would contain the following before and after JSON objects:

```js
/* Before */
{
    "nick": "Johnny"
}

/* After */
{
    "nick": null
}
```

(See also: the [discord.py documention](https://discordpy.readthedocs.io/en/rewrite/api.html#audit-log-data)
on the subject)

### Crawl Tables
The tables `channel_crawl` and `audit_log_crawl` are used internally by the crawler to track how far along its progress is. These tables should not be used by clients, and their schemas can change at any time for any reason.

### Emoji Data
The distinction between "`emoji_id`" and "`emoji_unicode`" exists because Discord labels two very different objects as "emojis". One are "native" emojis, which are really unicode "characters"\*. The other are "discord" or custom emojis, which are an image uploaded to a particular Discord guild. They have an assigned emoji ID and a name. Custom emojis are always attached to a guild, and may also be provided from outside sources, such as Twitch.

To capture this union of two different types, two columns are used. If the emote is a unicode one, then the `emoji_id` column is set to `0` and the `emoji_unicode` column is a literal copy of the unicode string presented as the emoji. Likewise, if the emote is a custom one, the `emoji_id` is set to that emoji's globally unique ID and the `emoji_unicode` column is set to an empty string.

\* Unicode emojis may be more than one code point, as it may have modifiers like skin tone, or be composite emojis, such as the US flag, which is made of regional indicator characters, including spacer characters in between. For this reason, the type of the `emoji_unicode` column is `Unicode(7)`.
