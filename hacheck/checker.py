import time

import tornado.concurrent
import tornado.gen
import tornado.httpclient

from . import cache
from . import __version__

TIMEOUT = 10


@tornado.gen.coroutine
def check(service_name, port, query, request):
    now = time.time()
    with cache.maybe_bust(request.headers.get('Pragma', '') == 'no-cache'):
        try:
            raise tornado.gen.Return(cache.get(service_name, port, query, now))
        except KeyError:
            request = tornado.httpclient.HTTPRequest("http://127.0.0.1:%d/%s" % (port, query), method="GET",
                    headers={"User-Agent": "hastate %s" % (__version__)}, request_timeout=TIMEOUT)
            http_client = tornado.httpclient.AsyncHTTPClient()
            response = yield http_client.fetch(request)
            value = (response.code, response.body)
            cache.set(service_name, port, query, value)
            raise tornado.gen.Return((value[0], value[1]))
