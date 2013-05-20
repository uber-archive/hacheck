import contextlib
import copy
import time
from collections import Counter
from collections import OrderedDict

_cache = OrderedDict()

_make_key = lambda *args: tuple(args)

config = {
    'cache_time': 10,
    'ignore_cache': False,
}

stats = Counter({
    'expirations': 0,
    'sets': 0,
    'gets': 0,
    'hits': 0,
    'misses': 0
})


def configure(cache_time):
    config['cache_time'] = cache_time


def get(service, port, query, now):
    """Get a key from the cache

    :param service: The name of the service
    :param port: The port the service is listening on
    :param query: The query string
    :param now: The current time
    :raises: KeyError if the key is not present or has expired
    :returns: The result
    """
    key = _make_key(service, port, query)
    stats['gets'] += 1
    if key in _cache:
        expiry, result = _cache[key]
        if expiry >= now and not config['ignore_cache']:
            stats['hits'] += 1
            return result
        else:
            stats['expirations'] += 1
            del _cache[key]
    stats['misses'] += 1
    raise KeyError(key)


def set(service, port, query, value):
    key = _make_key(service, port, query)
    stats['sets'] += 1
    expiration_time = time.time() + config['cache_time']
    _cache[key] = (expiration_time, value)


def get_stats():
    return copy.copy(stats)


@contextlib.contextmanager
def maybe_bust(bust_or_not):
    previous_state = config['ignore_cache']
    config['ignore_cache'] = bust_or_not
    yield
    config['ignore_cache'] = previous_state
