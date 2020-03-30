#
# __main__.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017-2018 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import argparse
import logging
import sys

from .client import EventIngestionClient
from .config import load_config
from .crawler import AuditLogCrawler, HistoryCrawler
from .sql import DiscordSqlHandler

__all__ = [
    'LOG_FILE',
    'LOG_FILE_MODE',
]

LOG_FILE = 'bot.log'
LOG_FILE_MODE = 'w'
LOG_FORMAT = "[%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "[%d/%m/%Y %H:%M:%S]"

class StderrTee:
    __slots__ = (
        'fh',
        'stderr',
    )

    def __init__(self, filename, mode):
        self.fh = open(filename, mode)
        self.stderr = sys.stderr

    def __del__(self):
        sys.stderr = self.stderr
        self.fh.close()

    def write(self, data):
        self.fh.write(data)
        self.stderr.write(data)

ERR_FILE = 'errors.log'
ERR_FILE_MODE = 'w'

sys.stderr = StderrTee(ERR_FILE, ERR_FILE_MODE)

if __name__ == '__main__':
    # Parse arguments
    argparser = argparse.ArgumentParser(description='Bot to track posting data')
    argparser.add_argument('-q', '--quiet', '--no-stdout',
            dest='stdout', action='store_false',
            help="Don't output to standard out.")
    argparser.add_argument('-v', '--verbose',
            dest='verbose', action='count',
            help="Increase the logger's verbosity.")
    argparser.add_argument('-d', '--debug',
            dest='debug', action='store_true',
            help="Set logging level to debug.")
    argparser.add_argument('-g', '--guild-id',
            dest='guild_ids', action='append', type=int,
            help="Override the list of guild IDs to look at.")
    argparser.add_argument('-B', '--batch-size',
            dest='batch_size', type=int,
            help="Override the batch size used during crawling.")
    argparser.add_argument('-Q', '--queue-size',
            dest='queue_size', type=int,
            help="Override the queue size used during crawling.")
    argparser.add_argument('-Y', '--yield-delay',
            dest='yield_delay', type=float,
            help="Override the yield delay during crawling.")
    argparser.add_argument('-E', '--empty-source-delay',
            dest='empty_source_delay', type=float,
            help="Override the empty source delay during crawling.")
    argparser.add_argument('-T', '--token', dest='token',
            help="Override the bot token used to log in.")
    argparser.add_argument('-U', '--db-url', dest='db_url',
            help="Override the database URL to connect to.")
    argparser.add_argument('config_file',
            help="Specify a configuration file to use. Keep it secret!")
    args = argparser.parse_args()

    # Set up logging
    log_fmtr = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    log_hndl = logging.FileHandler(filename=LOG_FILE, mode=LOG_FILE_MODE)
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

    # Map logging to outputs
    main_logger.addHandler(log_hndl)
    if args.debug:
        discord_logger.addHandler(log_hndl)

    if args.stdout:
        log_out_hndl = logging.StreamHandler(sys.stdout)
        log_out_hndl.setFormatter(log_fmtr)
        main_logger.addHandler(log_out_hndl)
        if args.debug:
            discord_logger.addHandler(log_out_hndl)

    # Get and verify configuration
    config, valid = load_config(args.config_file, main_logger)
    if not valid:
        main_logger.error("Configuration file was invalid.")
        sys.exit(1)

    # Override configuration settings
    verbosity = getattr(args, 'verbosity', 0)
    if verbosity >= 1:
        config['logger']['full-messages'] = True
    if verbosity >= 2:
        config['logger']['ignored-events'] = True
    if verbosity >= 3:
        discord_logger.addHandler(log_hndl)

    if args.guild_ids is not None:
        config['guild-ids'] = args.guild_ids

    if args.batch_size is not None:
        config['crawler']['batch-size'] = args.batch_size

    if args.queue_size is not None:
        config['crawler']['queue-size'] = args.queue_size

    if args.yield_delay is not None:
        config['crawler']['delays']['yield'] = args.yield_delay

    if args.empty_source_delay is not None:
        config['crawler']['delays']['empty-source'] = args.empty_source_delay

    if args.token is not None:
        config['bot']['token'] = args.token

    if args.db_url is not None:
        config['bot']['db-url'] = args.db_url

    # Create SQL handler
    sql = DiscordSqlHandler(config['bot']['db-url'], config['cache'], sql_logger)

    # Create client
    main_logger.info("Setting up bot")
    client = EventIngestionClient(config, sql, event_logger)
    main_logger.info("Starting bot, waiting for discord.py...")

    # Create crawlers
    hist_crawler = HistoryCrawler(client, sql, config, crawler_logger)
    hist_crawler.start()
    audit_crawler = AuditLogCrawler(client, sql, config, crawler_logger)
    audit_crawler.start()

    # Start main loop
    client.run_with_token()
