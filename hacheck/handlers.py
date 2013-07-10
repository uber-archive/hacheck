import logging
import time

import tornado.ioloop
import tornado.httputil
import tornado.httpclient
import tornado.gen
import tornado.web

from . import cache
from . import checker

log = logging.getLogger('hacheck')


class StatusHandler(tornado.web.RequestHandler):
    def get(self):
        stats = {}
        stats['cache'] = cache.get_stats()
        stats['uptime'] = time.time() - self.settings['start_time']
        self.set_status(200)
        self.write(stats)


class BaseServiceHandler(tornado.web.RequestHandler):
    CHECKERS = []

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self, service_name, port, query):
        with cache.maybe_bust(self.request.headers.get('Pragma', '') == 'no-cache'):
            port = int(port)
            last_message = ""
            for checker in self.CHECKERS:
                code, message = yield checker(service_name, port, query, io_loop=tornado.ioloop.IOLoop.current())
                last_message = message
                if code > 200:
                    if code in tornado.httputil.responses:
                        self.set_status(code)
                    else:
                        self.set_status(503)
                    self.write(message)
                    self.finish()
                    break
            else:
                self.set_status(200)
                self.write(last_message)
                self.finish()


class SpoolServiceHandler(BaseServiceHandler):
    CHECKERS = [checker.check_spool]


class HTTPServiceHandler(BaseServiceHandler):
    CHECKERS = [checker.check_spool, checker.check_http]


class TCPServiceHandler(BaseServiceHandler):
    CHECKERS = [checker.check_spool, checker.check_tcp]
