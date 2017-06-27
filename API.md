## API
The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL
NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED",  "MAY", and
"OPTIONAL" in this document are to be interpreted as described in
[RFC 2119](https://www.ietf.org/rfc/rfc2119.txt).

This document will try and only record information that is guaranteed.
There may be features or tables that exist but are not mentioned in
this document. This is likely intentional, as they are not yet ready
for public usage.

The database has two groups of tables, data tables and lookup tables.
Data tables are for information that are continually added, such
as messages and reactions. The lookup tables are for information like
users and channels, things that do not change regularly, and when they
do, are more likely to modify an existing entry than create/delete one.

### Guarantees and Requirements
* Clients should review this document whenever the minor version changes.
* Clients must not assume that any particular row is present. This is true
for all tables ane data points.
* Clients must be able to handle tables with information from multiple guilds.
* Clients must assume that there will be holes in the chronological history
of the records.
* Clients must not except queried data to be in chronological order, unless
they explicitly designate a `SORT BY` clause to do so.
* Except in the case where an explicit timestamp field is provided, or in the
case of emojis, clients shall determine timestamps from the snowflake provided
with each record.

### Table Schemas
The schemas are not yet stabilized, but applications may assume they will
stay the same. This message will be updated when as schemas are frozen.

(TODO)

### OAuth2
(Not implemented yet)

