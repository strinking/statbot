#
# util.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017-2018 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import hashlib
import struct

__all__ = [
    'null_logger',
    'int_hash',
]

class _NullLogger:
    __slots__ = ()

    def __init__(self):
        pass

    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

null_logger = _NullLogger()

def int_hash(n):
    bytez = struct.pack('>q', n)
    hashbytes = hashlib.sha512(bytez).digest()
    result, = struct.unpack('>q', hashbytes[24:32])
    return result
