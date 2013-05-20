import time

import tornado.httpclient
import tornado.gen
import tornado.web

from . import cache
from . import spool
from . import checker


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
        port = int(port)
        up, extra_info = spool.is_up(service_name)
        if not up:
            info_string = "Service %s in down state: %s" % (extra_info["service"], extra_info["reason"])
            self.write(info_string)
            self.set_status(503)
        else:
            code, message = yield checker.check(service_name, port, query, self.request)
            self.set_status(code)
            self.write(message)
            self.finish()
