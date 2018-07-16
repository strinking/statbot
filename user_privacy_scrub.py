#!/usr/bin/env python3.6

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

from collections import namedtuple
import logging
import sys

import yaml

import statbot

FakeUser = namedtuple('FakeUser', ('id', 'name'))

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} config-file user-id")
        exit(1)

    with open(sys.argv[1], 'r') as fh:
        config = yaml.safe_load(fh)

    # Get arguments
    db_url = config['bot']['db-url']
    user_id = int(sys.argv[2])

    # Set up logging
    logger = logging.getLogger('statbot.script.user_privacy_scrub')
    logger.setLevel(logging.INFO)
    log_hndl = logging.StreamHandler(sys.stdout)
    log_hndl.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(log_hndl)

    # Open database connection
    logger.info("Preparation done, starting user privacy scrub procedure...")
    sql = statbot.sql.DiscordSqlHandler(db_url, None, logger)
    sql.privacy_scrub(FakeUser(id=user_id, name=str(user_id)))
    logger.info("Done! Exiting...")
