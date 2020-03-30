#
# cache.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017-2018 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

from collections import OrderedDict
from collections.abc import MutableMapping

__all__ = [
    'LruCache',
]

class LruCache(MutableMapping):
    __slots__ = (
        'store',
        'max_size',
    )

    def __init__(self, max_size=None):
        self.store = OrderedDict()
        self.max_size = max_size

    def __getitem__(self, key):
        obj = self.store.pop(key)
        self.store[key] = obj
        return obj

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key, value):
        self.store.pop(key, None)
        self.store[key] = value

        while len(self) > self.max_size:
            self.store.popitem(last=False)

    def __delitem__(self, key):
        del self.store[key]

    def __contains__(self, key):
        return key in self.store

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)
