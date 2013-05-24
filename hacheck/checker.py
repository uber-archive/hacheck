import datetime
import socket
import time

import tornado.concurrent
import tornado.ioloop
import tornado.gen
import tornado.httpclient

from . import cache
from . import spool
from . import __version__

TIMEOUT = 10


# Do not cache spool checks
@tornado.concurrent.return_future
def check_spool(service_name, port, query, io_loop, callback):
    up, extra_info = spool.is_up(service_name)
    if not up:
        info_string = 'Service %s in down state' % (extra_info['service'],)
        if extra_info.get('reason', ''):
            info_string += ": %s" % extra_info['reason']
        callback((503, info_string))
    else:
        callback((200, extra_info.get('reason', '')))


# IMPORTANT: the gen.coroutine decorator needs to be the innermost
@cache.cached
@tornado.gen.coroutine
def check_http(service_name, port, query, io_loop):
    if not query.startswith("/"):
        query = "/" + query  # pragma: no cover
    request = tornado.httpclient.HTTPRequest('http://127.0.0.1:%d%s' % (port, query), method='GET',
            headers={'User-Agent': 'hastate %s' % (__version__)}, request_timeout=TIMEOUT)
    http_client = tornado.httpclient.AsyncHTTPClient(io_loop=io_loop)
    try:
        response = yield http_client.fetch(request)
        code = response.code
        reason = response.body
    except tornado.httpclient.HTTPError as exc:
        code = exc.code
        reason = exc.response.body if exc.response else ""
    raise tornado.gen.Return((code, reason))


@cache.cached
@tornado.gen.coroutine
def check_tcp(service_name, port, query, io_loop):
    stream = None
    connect_start = time.time()

    def timed_out():
        try:
            stream.close()
        except:  # pragma: no cover
            pass
        raise tornado.gen.Return((503, 'Connection timed out after %.2fs' % (time.time() - connect_start)))

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    stream = tornado.iostream.IOStream(s, io_loop=io_loop)
    timeout = io_loop.add_timeout(datetime.timedelta(seconds=TIMEOUT), timed_out)
    yield tornado.gen.Task(stream.connect, ("127.0.0.1", port))
    io_loop.remove_timeout(timeout)
    stream.close()
    raise tornado.gen.Return((200, 'Connected in %.2fs' % (time.time() - connect_start)))
