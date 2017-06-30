#
# __main__.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import argparse
import asyncio
import json
import logging
import sys

from .client import EventIngestionClient
from .config import load_config
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
    argparser = argparse.ArgumentParser(description='Bot to track posting data')
    argparser.add_argument('-q', '--quiet', '--no-stdout',
            dest='stdout', action='store_false',
            help="Don't output to standard out.")
    argparser.add_argument('-l', '--include-log',
            dest='loglist', type=str, nargs='*',
            help="Specify which logs you want outputted.")
    argparser.add_argument('-d', '--debug',
            dest='debug', action='store_true',
            help="Set logging level to debug.")
    argparser.add_argument('config_file',
            help="Specify a configuration file to use. Keep it secret!")
    args = argparser.parse_args()

    # Set up logging
    log_fmtr = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    log_hndl = logging.FileHandler(filename=LOG_FILE,
            encoding='utf-8', mode=LOG_FILE_MODE)
    log_hndl.setFormatter(log_fmtr)
    log_level = (logging.DEBUG if args.debug else logging.INFO)

    # Create instances
    def get_logger(name, level=log_level):
        logger = logging.getLogger(name)
        logger.setLevel(level=level)
        return logger

    discord_logger = get_logger('discord', logging.INFO)
    main_logger = get_logger('statbot')
    event_logger = get_logger('statbot.event')
    crawler_logger = get_logger('statbot.crawler')
    sql_logger = get_logger('statbot.sql')
    del get_logger

    # Enable specified logs
    if args.loglist is None:
        loggers = [main_logger, event_logger, crawler_logger, sql_logger]
        if args.debug:
            loggers.append(discord_logger)
    else:
        logger_names = {
            'discord': discord_logger,
            'main': main_logger,
            'event': event_logger,
            'crawler': crawler_logger,
            'sql': sql_logger,
        }
        try:
            loggers = [logger_names[logname] for logname in args.loglist]
        except KeyError:
            print(f"No such logger: {logname}")
            exit(1)

    # Map to outputs
    for logger in loggers:
        logger.addHandler(log_hndl)

    if args.stdout:
        log_out_hndl = logging.StreamHandler(sys.stdout)
        log_out_hndl.setFormatter(log_fmtr)
        for logger in loggers:
            logger.addHandler(log_out_hndl)

    # Get and verify configuration
    config, valid = load_config(args.config_file, main_logger)
    if not valid:
        main_logger.error("Configuration file was invalid.")
        exit(1)

    # Open and run event client
    main_logger.info("Setting up bot")
    client = EventIngestionClient(config, event_logger, sql_logger=sql_logger)
    main_logger.info("Starting bot, waiting for discord.py...")
    client.run()

