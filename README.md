## discord-analytics
A [Discord](https://discordapp.com) selfbot that reads in posts from a given set
of servers and stores it in a SQL database. This application has two parts: the
listener, which ingests raw data from the Discord API, and the crawler, which
walks through the database and applies a function on it.

Available under the terms of the MIT License.

### Requirements
* Python 3.6 or later
* [discord.py (rewrite branch)](https://github.com/Rapptz/discord.py)
* [SQLAlchemy](http://www.sqlalchemy.org/)

### Execution
```
docker run --name postgresql -itd --restart always \
  --env 'PG_PASSWORD=[your_password_here]' \
  --publish 5432:5432 \
  --volume /srv/docker/postgresql:/var/lib/postgresql \
  sameersbn/postgresql:9.6-2

python3 -m discordstats [-q] [-d] config_file.json
```

