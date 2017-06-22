## discord-analytics
A [Discord](https://discordapp.com) selfbot that reads in posts from a given set
of servers and stores it in a SQL database. This application has two parts: the
listener, which ingests raw data from the Discord API, and the crawler, which
walks through the database and applies a function on it.

Available under the terms of the MIT License.

### Requirements
* Python 3.5 or later
* [discord.py (rewrite branch)](https://github.com/Rapptz/discord.py)
* [SQLAlchemy](http://www.sqlalchemy.org/)

### Execution
```
python3 -m discord-analytics [-q] [-d] [-s AUTH_FILE] [-c CONFIG] SQL_DB_FILE
```

