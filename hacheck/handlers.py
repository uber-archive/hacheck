import time

import tornado.ioloop
import tornado.httpclient
import tornado.gen
import tornado.web

from . import cache
from . import checker


class StatusHandler(tornado.web.RequestHandler):
    def get(self):
        stats = {}
        stats['cache'] = cache.get_stats()
        stats['uptime'] = time.time() - self.settings['start_time']
        self.set_status(200)
        self.write(stats)


class BaseServiceHandler(tornado.web.RequestHandler):
    CHECKERS = [checker.check_spool]

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self, service_name, port, query):
        with cache.maybe_bust(self.request.headers.get('Pragma', '') == 'no-cache'):
            port = int(port)
            last_message = ""
            for checker in self.CHECKERS:
                code, message = yield checker(service_name, port, query, io_loop=tornado.ioloop.IOLoop.instance())
                last_message = message
                if code > 500:
                    self.set_status(code)
                    self.write(message)
                    self.finish()
                    break
            else:
                self.set_status(200)
                self.write(last_message)
                self.finish()


class HTTPServiceHandler(BaseServiceHandler):
    CHECKERS = [checker.check_spool, checker.check_http]


class TCPServiceHandler(BaseServiceHandler):
    CHECKERS = [checker.check_spool, checker.check_tcp]
