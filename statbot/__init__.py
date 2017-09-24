#
# __init__.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

from . import client, config, message_utils, range, sql, util

__all__ = [
    '__version__',
    'client',
    'config',
    'message_history',
    'message_utils',
    'range',
    'sql',
    'util',
]

__version__ = '0.2.0'
