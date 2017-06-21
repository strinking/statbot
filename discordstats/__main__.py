#
# __main__.py
#
# discord-analytics - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# discord-analytics is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import argparse
import asyncio
import discord
import json
import logging
import sys

from .config import DEFAULT_CONFIG, load_config
from .sql import DiscordSqlHandler
from .util import plural

__all__ = [
    'LOG_FILE',
    'LOG_TO_STDOUT',
    'LOG_FILE_MODE',
]

LOG_FILE = 'bot.log'
LOG_FILE_MODE = 'w'
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "[%d/%m/%Y %H:%M]"

if __name__ == '__main__':
    # Parse arguments
    argparser = argparse.ArgumentParser(description='Self-bot to track posting data')
    argparser.add_argument('-q', '--quiet', '--no-stdout',
            dest='stdout', action='store_false',
            help="Don't output to standard out.")
    argparser.add_argument('-d', '--debug',
            dest='debug', action='store_true',
            help="Set logging level to debug.")
    argparser.add_argument('-s', '--secret',
            dest='auth_file', nargs='?', default='client_secret.json',
            help="The JSON file with all the Discord authentication data. Keep it secret!")
    argparser.add_argument('-c', '--conf', '--config',
            dest='config_file', nargs='?',
            help="Specify a configuration file to use")
    argparser.add_argument('sql-database-file',
            help="The database file to store the records in")
    args = argparser.parse_args()

    # Set up logging
    logger = logging.getLogger('discord')
    logger.setLevel(level=(logging.DEBUG if args.debug else logging.INFO))
    log_fmtr = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    log_hndl = logging.FileHandler(filename=LOG_FILE, encoding='utf-8', mode=LOG_FILE_MODE)
    log_hndl.setFormatter(log_fmtr)
    logger.addHandler(log_hndl)

    if args.stdout:
        log_hndl = logging.StreamHandler(sys.stdout)
        log_hndl.setFormatter(log_fmtr)
        logger.addHandler(log_hndl)

    # Get and verify configuration
    if args.config_file is None:
        logger.info("No configuration file passed. Using default...")
        cfg = DEFAULT_CONFIG
    else:
        cfg, valid = load_config(args.config_file)
        if not valid:
            logger.error("Configuration file was invalid.")
            exit(1)

    # Open client
    bot = discord.Client()
    bot.sql = None

    @bot.async_event
    def on_ready():
        # Print welcome string
        logger.info("Logged in as {} ({})".format(bot.user.name, bot.user.id))

        # Set up SQL interface
        db = getattr(args, 'sql-database-file')
        bot.sql = DiscordSqlHandler(db, logger)

        # All done setting up
        logger.info("Ready!")

    @bot.async_event
    def on_message(message):
        logger.debug("Received message id {}".format(message.id))

        if bot.sql is None:
            logger.warn("Can't log message, not ready yet!")
            return
        elif message.channel.is_private or message.server.id not in cfg['servers']:
            logger.debug("Ignoring message.")
            return

        logger.info("Message from {}#{} in {} #{}: {}".format(
            message.author.name,
            message.author.discriminator,
            message.server.name,
            message.channel.name,
            message.content))
        bot.sql.ingest_message(message)

    # Get authentication token
    with open(args.auth_file, 'r') as fh:
        token = json.load(fh)['token']

    # Run the bot
    bot.run(token, bot=False)

