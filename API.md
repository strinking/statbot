## API
The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL
NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED",  "MAY", and
"OPTIONAL" in this document are to be interpreted as described in
[RFC 2119](https://www.ietf.org/rfc/rfc2119.txt).

This document will try and only record information that is guaranteed.
There may be features or tables that exist but are not mentioned in
this document. This is likely intentional, as they are not yet ready
for public usage.

The database has a few different categories of tables.
**Data tables** are for information that is continually added, such
as message and reactions.  
**Lookup tables** are for static information, such as information about
channels or guilds. While these may get updated, they will not do so
frequently, and do not always track history.  
**ORM tables** are for internal use of the bot to track information. These
tables will _not_ have stable schemas and should not be used by end users
to gather information.

### Guarantees and Requirements
* Clients should review this document whenever the minor version changes.
* Clients must be able to handle tables with information from multiple guilds.
* Clients must assume that there may be holes in the chronological history
of the records.
* Clients must not expect queried data to be in chronological order, unless
they explicitly designate a `SORT BY` clause to do so.
* Except in the case where an explicit timestamp field is provided,
clients shall determine timestamps from the snowflake provided with each record.

### Table Schemas
The schemas are not yet stabilized, but applications may assume they will
stay the same. This message will be updated when as schemas are frozen.

(TODO)

### OAuth2
(Not implemented yet)

