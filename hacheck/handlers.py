import collections
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

StatusResponse = collections.namedtuple('StatusResponse', ['code', 'remote_ip', 'ts'])

if hasattr(collections, 'Counter'):
    Counter = collections.Counter  # fast
else:
    def Counter():
        return collections.defaultdict(lambda: 0)

seen_services = {}
service_count = collections.defaultdict(Counter)
last_statuses = {}


def _reset_stats():
    seen_services.clear()
    service_count.clear()
    last_statuses.clear()


class StatusHandler(tornado.web.RequestHandler):
    def get(self):
        stats = {}
        stats['cache'] = cache.get_stats()
        stats['uptime'] = time.time() - self.settings['start_time']
        self.set_status(200)
        self.write(stats)


class ListRecentHandler(tornado.web.RequestHandler):
    def get(self):
        now = time.time()
        recency_threshold = int(self.get_argument('threshold', 10 * 60))
        response = []
        for service_name, t in seen_services.items():
            if now - t > recency_threshold:
                continue
            last_status = last_statuses.get(service_name, None)
            if last_status is not None:
                last_status = last_status._asdict()
            response.append((service_name, last_status))
        self.write({
            'seen_services': list(sorted(response)),
            'threshold_seconds': recency_threshold
        })


class ServiceCountHandler(tornado.web.RequestHandler):
    def get(self):
        self.write({'service_access_counts': dict(service_count)})


class BaseServiceHandler(tornado.web.RequestHandler):
    CHECKERS = []

    def maybe_get_port_from_haproxy_server_state(self):
        """
        Look for the 'X-Haproxy-Server-State' header and try to parse out the
        'port' value.

        Note that only very recent versions of HAProxy support sending
        the port in the send-state header. In particular you need
        commit 514061c414080701cb046171041a2d00859660e8 from haproxy dev.

        Example server state header:

            X-Haproxy-Server-State: UP 2/3; address=srv2; port=1234;
              name=bck/srv2; node=lb1; weight=1/2; scur=13/22; qcur=0

        returns: the string-typed port if found, else None.
        """

        server_state = self.request.headers.get('X-Haproxy-Server-State', '')

        parts = server_state.split(';')
        parts = [part.strip() for part in parts]
        parts = [part.split('=') for part in parts]
        parts = [part for part in parts if len(part) == 2]

        return dict(parts).get('port')

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self, service_name, port, query):
        port = self.maybe_get_port_from_haproxy_server_state() or port

        seen_services[service_name] = time.time()
        service_count[service_name][self.request.remote_ip] += 1
        with cache.maybe_bust(self.request.headers.get('Pragma', '') == 'no-cache'):
            port = int(port)
            last_message = ""
            querystr = self.request.query
            for this_checker in self.CHECKERS:
                code, message = yield this_checker(
                    service_name,
                    port,
                    query,
                    io_loop=tornado.ioloop.IOLoop.current(),
                    query_params=querystr,
                    headers=self.request.headers,
                )
                last_message = message
                if code > 200:
                    last_statuses[service_name] = StatusResponse(code, self.request.remote_ip, time.time())
                    if code in tornado.httputil.responses:
                        self.set_status(code)
                    else:
                        self.set_status(503)
                    self.write(message)
                    self.finish()
                    break
            else:
                last_statuses[service_name] = StatusResponse(200, self.request.remote_ip, time.time())
                self.set_status(200)
                self.write(last_message)
                self.finish()


class SpoolServiceHandler(BaseServiceHandler):
    CHECKERS = [checker.check_spool]


class HTTPServiceHandler(BaseServiceHandler):
    CHECKERS = [checker.check_spool, checker.check_http]


class TCPServiceHandler(BaseServiceHandler):
    CHECKERS = [checker.check_spool, checker.check_tcp]


class MySQLServiceHandler(BaseServiceHandler):
    CHECKERS = [checker.check_spool, checker.check_mysql]
