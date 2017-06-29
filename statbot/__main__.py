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
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(level=logging.INFO)

    main_logger = logging.getLogger('main')
    main_logger.setLevel(level=log_level)

    event_logger = logging.getLogger('event')
    event_logger.setLevel(level=log_level)

    sql_logger = logging.getLogger('sql')
    sql_logger.setLevel(level=log_level)

    # Enable specified logs
    if args.loglist is None:
        loggers = [main_logger, event_logger, sql_logger]
        if args.debug:
            loggers.append(discord_logger)
    else:
        logger_names = {
            'main': main_logger,
            'discord': discord_logger,
            'event': event_logger,
            'sql': sql_logger,
        }
        try:
            loggers = [logger_names[logname] for logname in args.loglist]
        except KeyError:
            print(f"No such logger: {logname}")
            exit(1)

    # Map to outputs
    map(lambda x: x.addHandler(log_hndl), loggers)

    if args.stdout:
        log_out_hndl = logging.StreamHandler(sys.stdout)
        log_out_hndl.setFormatter(log_fmtr)
        map(lambda x: x.addHandler(log_out_hndl), loggers)

    # Get and verify configuration
    config, valid = load_config(args.config_file, main_logger)
    if not valid:
        main_logger.error("Configuration file was invalid.")
        exit(1)

    # Open and run event client
    main_logger.info("Starting bot...")
    client = EventIngestionClient(config, event_logger, sql_logger=sql_logger)
    client.run()

