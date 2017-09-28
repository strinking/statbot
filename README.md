## statbot
A [Discord](https://discordapp.com) bot that reads in posts from a given set
of servers and stores it in a SQL database. This application has two parts: the
listener, which ingests raw data as it arrives, and the crawler, which walks
through past history of Discord messages and adds them.

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
pip3 install -r requirements.txt
```

### Execution
After preparing a configuration file, (see `misc/sample_config.json`)
you can call the program as follows:
```sh
python3 -m statbot [-q] [-d] your_config_file.json
```

A sample `docker-compose.yaml` configuration is also provided in `misc/` in case you would
like to host your PostgreSQL database via Docker.

### Questions
**How do I use statbot as a selfbot?**

You shouldn't. Each person who you collect data from must explicitly agree to it. If you are
running a server you have the ability to enforce this, but that also means you may as well
just use an actual bot account. We will not support forks that add selfbot support to statbot,
and we will not accept patches that do so either.

