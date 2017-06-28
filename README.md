## statbot
A [Discord](https://discordapp.com) bot/selfbot that reads in posts from a given set
of servers and stores it in a SQL database. This application has two parts: the
listener, which ingests raw data as it arrives, and the crawler, which walks
through past history of Discord events and adds them.

This bot is designed for use with Postgres, but in principle could be used
with any database that SQLAlchemy supports.

Available under the terms of the MIT License.

### Requirements
* Python 3.6 or later
* [discord.py (rewrite branch)](https://github.com/Rapptz/discord.py)
* [SQLAlchemy](http://www.sqlalchemy.org/)
* [psycopg2](https://pypi.python.org/pypi/psycopg2)

You can install them all using pip by running:
```sh
pip3 -r requirements.txt
```

### Execution
After preparing a configuration file, (see `misc/sample_config.json`)
you can call the program as follows:
```sh
python3 -m statbot [-q] [-d] your_config_file.json
```

