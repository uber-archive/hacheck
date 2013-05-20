import time

import tornado.httpclient
import tornado.gen
import tornado.web

from . import __version__
from . import cache
from . import spool

TIMEOUT = 10


class StatusHandler(tornado.web.RequestHandler):
    def get(self):
        stats = {}
        stats['cache'] = cache.get_stats()
        stats['uptime'] = time.time() - self.settings['start_time']
        self.set_status(200)
        self.write(stats)


class ServiceHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self, service_name, port, query):
        now = time.time()
        port = int(port)
        up, extra_info = spool.is_up(service_name)
        if not up:
            info_string = "Service %s in down state: %s" % (extra_info["service"], extra_info["reason"])
            self.write(info_string)
            self.set_status(503)
        else:
            with cache.maybe_bust(self.request.headers.get('Pragma', '') == 'no-cache'):
                try:
                    result_code, result_message = cache.get(service_name, port, query, now)
                    self.set_status(result_code)
                    self.write(result_message)
                    self.finish()
                except KeyError:
                    request = tornado.httpclient.HTTPRequest("http://127.0.0.1:%d/%s" % (port, query), method="GET",
                            headers={"User-Agent": "hastate %s" % (__version__)}, request_timeout=TIMEOUT)
                    http_client = tornado.httpclient.AsyncHTTPClient()
                    response = yield http_client.fetch(request)
                    value = (response.code, response.body)
                    cache.set(service_name, port, query, value)
                    self.write(value[1])
                    self.set_status(value[0])
                    self.finish()
