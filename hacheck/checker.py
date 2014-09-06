import datetime
import socket
import time

import tornado.concurrent
import tornado.ioloop
import tornado.iostream
import tornado.gen
import tornado.httpclient

from . import cache
from . import config
from . import mysql
from . import spool
from . import __version__

TIMEOUT = 10


class Timeout(Exception):
    pass


def add_timeout_to_task(func, args=tuple(), kwargs=dict(), timeout_secs=TIMEOUT, io_loop=None):
    # In tornado 4.0, this is really easy
    # (tornado.gen.with_timeout(gen.Task(func, args))
    #
    # asas, in tornado 3.x, we don't get a Future from gen.Task, we get
    # a Task object, which doesn't have an add_done_callback method of
    # any sort. So we're gonna hack the hell out of it by creating our own
    # Future object and populating it.
    future = tornado.concurrent.Future()

    def callback(*args, **kwargs):
        if args:
            result = args[0]
        else:
            result = None
        future.set_result(result)

    kwargs['callback'] = callback
    func(*args, **kwargs)

    def timed_out(*args, **kwargs):
        future.set_exception(Timeout('Timed out after %ds' % timeout_secs))

    if io_loop is None:
        io_loop = tornado.ioloop.IOLoop.current()
    timeout = io_loop.add_timeout(
        datetime.timedelta(seconds=timeout_secs),
        timed_out
    )
    io_loop.add_future(
        future, lambda f: io_loop.remove_timeout(timeout)
    )
    return future


# Do not cache spool checks
@tornado.concurrent.return_future
def check_spool(service_name, port, query, io_loop, callback, query_params):
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
def check_http(service_name, port, check_path, io_loop, query_params):
    qp = query_params
    if not check_path.startswith("/"):
        check_path = "/" + check_path  # pragma: no cover
    headers = {'User-Agent': 'hastate %s' % (__version__)}
    if config.config['service_name_header']:
        headers[config.config['service_name_header']] = service_name
    path = 'http://127.0.0.1:%d%s%s' % (port, check_path, '?' + qp if qp else '')
    request = tornado.httpclient.HTTPRequest(
        path,
        method='GET',
        headers=headers,
        request_timeout=TIMEOUT
    )
    http_client = tornado.httpclient.AsyncHTTPClient(io_loop=io_loop)
    try:
        response = yield http_client.fetch(request)
        code = response.code
        reason = response.body
    except tornado.httpclient.HTTPError as exc:
        code = exc.code
        reason = exc.response.body if exc.response else ""
    except Exception as e:
        code = 599
        reason = 'Unhandled exception %s' % e
    raise tornado.gen.Return((code, reason))


@cache.cached
@tornado.gen.coroutine
def check_tcp(service_name, port, query, io_loop, query_params):
    stream = None
    connect_start = time.time()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    try:
        stream = tornado.iostream.IOStream(s, io_loop=io_loop)
        yield add_timeout_to_task(
            stream.connect,
            args=[('127.0.0.1', port)],
            timeout_secs=TIMEOUT
        )
    except Timeout:
        raise tornado.gen.Return((
            503,
            'Connection timed out after %.2fs' % (time.time() - connect_start)
        ))
    finally:
        if stream:
            stream.close()
    raise tornado.gen.Return((
        200,
        'Connected in %.2fs' % (time.time() - connect_start)
    ))


@cache.cached
@tornado.gen.coroutine
def check_mysql(service_name, port, query, io_loop, query_params):
    username = config.config.get('mysql_username', None)
    password = config.config.get('mysql_password', None)
    if username is None or password is None:
        raise tornado.gen.Return((500, 'No MySQL username/pasword in config file'))

    def timed_out(duration):
        raise tornado.gen.Return((503, 'MySQL timed out after %.2fs' % (duration)))

    conn = mysql.MySQLClient(port=port, global_timeout=TIMEOUT, io_loop=io_loop)
    response = yield conn.connect(username, password)
    if not response.OK:
        raise tornado.gen.Return((500, 'MySQL sez %s' % response))
    yield conn.quit()
    raise tornado.gen.Return((200, 'MySQL connect response: %s' % response))


@cache.cached
@tornado.gen.coroutine
def check_redis(service_name, port, query, io_loop, query_params):
    stream = None
    connect_start = time.time()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    try:
        stream = tornado.iostream.IOStream(s, io_loop=io_loop)
        yield add_timeout_to_task(
            stream.connect,
            args=[('127.0.0.1', port)],
            timeout_secs=TIMEOUT
        )
        yield stream.write('PING\r\n')
        response = yield add_timeout_to_task(
            stream.read_until,
            args=['\n'],
            timeout_secs=TIMEOUT
        )
        stream.close()
        if response.strip() != '+PONG':
            raise tornado.gen.Return((500, 'Sent PING, got back %s' % response))
        else:
            raise tornado.gen.Return((200, 'Sent PING, got back +PONG'))
    except Timeout:
        raise tornado.gen.Return((
            503,
            'Connection timed out after %.2fs' % (time.time() - connect_start)
        ))
    finally:
        if stream:
            stream.close()
    raise tornado.gen.Return((
        200,
        'Connected in %.2fs' % (time.time() - connect_start)
    ))
