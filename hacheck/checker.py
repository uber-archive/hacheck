import csv
import datetime
import socket
import time
import re
import json

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

HTTP_HEADERS_TO_COPY = ('Host',)


class Timeout(Exception):
    pass


def add_timeout_to_connect(stream, args=tuple(), kwargs=dict(), timeout_secs=TIMEOUT, io_loop=None):
    # In tornado 4.0, this is really easy
    # (tornado.gen.with_timeout(gen.Task(func, args)) (where func is the connect method on a stream).
    #
    # But we want to support 3.x and we don't get anything useful there, so
    # we're hacking it ourselves.
    future = tornado.concurrent.Future()

    def callback(*args, **kwargs):
        if args:
            result = args[0]
        else:
            result = None
        future.set_result(result)

    def close_callback():
        if stream.error:
            future.set_exception(stream.error)

    kwargs['callback'] = callback
    stream.set_close_callback(close_callback)
    stream.connect(*args, **kwargs)
    if stream.closed() and stream.error:
        raise stream.error

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
def check_spool(service_name, port, query, io_loop, callback, query_params, headers):
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
def check_http(service_name, port, check_path, io_loop, query_params, headers):
    qp = query_params
    if not check_path.startswith("/"):
        check_path = "/" + check_path  # pragma: no cover
    headers_out = {'User-Agent': 'hastate %s' % (__version__)}
    for header in HTTP_HEADERS_TO_COPY:
        if header in headers:
            headers_out[header] = headers[header]
    if config.config['service_name_header']:
        headers_out[config.config['service_name_header']] = service_name
    path = 'http://127.0.0.1:%d%s%s' % (port, check_path, '?' + qp if qp else '')
    request = tornado.httpclient.HTTPRequest(
        path,
        method='GET',
        headers=headers_out,
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
def check_haproxy(service_name, port, check_path, io_loop, query_params, headers):
    path = 'http://127.0.0.1:%d/;csv' % (port,)
    request = tornado.httpclient.HTTPRequest(
        path,
        method='GET',
        request_timeout=TIMEOUT
    )
    http_client = tornado.httpclient.AsyncHTTPClient(io_loop=io_loop)
    try:
        response = yield http_client.fetch(request)
        code = response.code
        body = response.body.decode('utf-8')
        PXNAME = 0
        SVNAME = 1
        STATUS = 17
        service_present = False
        for row in csv.reader(body.split('\n')):
            if len(row) < 18:
                continue
            if row[PXNAME] == service_name and row[SVNAME] == 'BACKEND':
                if row[STATUS] == 'UP':
                    code = 200
                    reason = '%s is UP' % service_name
                else:
                    code = 500
                    reason = '%s is %s' % (service_name, row[STATUS])
                service_present = True
                break
        if not service_present:
            code = 500
            reason = '%s is not found' % service_name
    except tornado.httpclient.HTTPError as exc:
        code = exc.code
        reason = exc.response.body if exc.response else ""
    except Exception as e:
        code = 599
        reason = 'Unhandled exception %s %s %s' % (e, service_name, port)
    raise tornado.gen.Return((code, reason))


@cache.cached
@tornado.gen.coroutine
def check_tcp(service_name, port, query, io_loop, query_params, headers):
    stream = None
    connect_start = time.time()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    try:
        stream = tornado.iostream.IOStream(s, io_loop=io_loop)
        yield add_timeout_to_connect(
            stream,
            args=[('127.0.0.1', port)],
            timeout_secs=TIMEOUT
        )
    except Timeout:
        raise tornado.gen.Return((
            503,
            'Connection timed out after %.2fs' % (time.time() - connect_start)
        ))
    except socket.error as e:
        raise tornado.gen.Return((
            503,
            'Unexpected error %s after %2fs' % (e, time.time() - connect_start)
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
def check_mysql(service_name, port, query, io_loop, query_params, headers):
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


#
# Check a Redis (or Sentinel) instance.  Sends `cmd' to `port', reads data
# until `readuntil' is seen and then processes the result using `callback'.
#
@tornado.gen.coroutine
def check_redis(io_loop, port, cmd, readuntil, callback):
    stream = None
    connect_start = time.time()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    try:
        stream = tornado.iostream.IOStream(s, io_loop=io_loop)
        yield add_timeout_to_connect(
            stream,
            args=[('127.0.0.1', port)],
            timeout_secs=TIMEOUT
        )

        if re.match(r'(3.)', tornado.version) is not None:
            # Tornado V3
            redis_future = tornado.concurrent.Future()

            def write_callback():
                def read_callback(data):
                    stream.close()

                    r = callback(data)
                    redis_future.set_result(r)

                stream.read_until(readuntil, read_callback)
            stream.write(cmd, write_callback)

            result = yield redis_future
            raise tornado.gen.Return(result)

        if re.match(r'(4.)', tornado.version) is not None:
            # Tornado V4
            yield stream.write(cmd)
            data = yield stream.read_until(readuntil)
            stream.close()
            raise tornado.gen.Return(callback(data))

    except Timeout:
        raise tornado.gen.Return((
            503,
            'Connection timed out after %.2fs' % (time.time() - connect_start)
        ))
    raise tornado.gen.Return((
        200,
        'Connected in %.2fs' % (time.time() - connect_start)
    ))

@cache.cached
@tornado.gen.coroutine
def check_redis_sentinel(service_name, port, query, io_loop, query_params, headers):
    def cb(data):
        if data.strip() != b'+PONG':
            return (500, 'Sent PING, got back %s' % data)
        else:
            return (200, 'Sent PING, got back +PONG')

    r = yield check_redis(io_loop, port, b'PING\r\n', b'\n', cb)
    raise tornado.gen.Return(r)

#
# Generate a callback for processing redis or sentinel INFO data.
#
def gen_info_cb(is_sentinel, query, query_params):
    try:
        from urllib.parse import parse_qs
    except ImportError:
        from urlparse import parse_qs

    mdict = {}
    if query == 'match':
        mdict = parse_qs(query_params)

    def cb(data):
        info = {}

        for line in data.decode('utf-8').split('\n'):
            if is_sentinel:
                ipport = re.findall(r'\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}:\d{1,5}',
                                    line)
                if ipport:
                    try:
                         k="redis_master"
                         v=ipport[0]
                         info[k]=v
                    except ValueError:
                        continue
            if ':' in line:
                try:
                    k,v = line.strip().split(':')
                    info[k] = v
                except ValueError:
                    continue

        if info['redis_version'] == None:
            return (500, 'Sent INFO, got back %s' % data)

        # If we are not doing a 'match' query, then we just return the
        # INFO result.
        if not mdict:
            return (200, json.dumps(info))

        for k, vals in mdict.iteritems():
            for v in vals:
                try:
                    if info[k] == v:
                        return (200, 'Match found: field %s, value %s' %
                                (k, v))
                except:
                    pass

        return (500, 'No matching field found')

    return cb


@cache.cached
@tornado.gen.coroutine
def check_redis_info(service_name, port, query, io_loop, query_params, headers):
    cb = gen_info_cb(False, query, query_params)
    r = yield check_redis(io_loop, port, b'INFO\r\n', b'Keyspace', cb)
    raise tornado.gen.Return(r)

@cache.cached
@tornado.gen.coroutine
def check_sentinel_info(service_name, port, query, io_loop, query_params, headers):
    cb = gen_info_cb(True, query, query_params)
    r = yield check_redis(io_loop, port, b'INFO\r\n', b'sentinels', cb)
    raise tornado.gen.Return(r)
