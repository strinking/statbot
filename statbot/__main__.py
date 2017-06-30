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

class StderrTee:
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
    argparser.add_argument('-N', '--no-sql-logs',
            dest='sql_logs', action='store_false',
            help="Only output the discord logger output.")
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

    dis_logger = logging.getLogger('discord')
    dis_logger.setLevel(level=log_level)
    dis_logger.addHandler(log_hndl)

    sql_logger = logging.getLogger('sql')
    sql_logger.setLevel(level=log_level)
    sql_logger.addHandler(log_hndl)

    if args.stdout:
        log_hndl = logging.StreamHandler(sys.stdout)
        log_hndl.setFormatter(log_fmtr)
        dis_logger.addHandler(log_hndl)
        if args.sql_logs:
            sql_logger.addHandler(log_hndl)

    # Get and verify configuration
    config, valid = load_config(args.config_file, dis_logger)
    if not valid:
        dis_logger.error("Configuration file was invalid.")
        exit(1)

    # Open and run client
    dis_logger.info("Starting bot...")
    client = EventIngestionClient(config, dis_logger, sql_logger=sql_logger)
    client.run()

