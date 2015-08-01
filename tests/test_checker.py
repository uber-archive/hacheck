import mock
import socket

try:
    from unittest2 import TestCase
except ImportError:
    from unittest import TestCase

import tornado.concurrent
import tornado.web
import tornado.testing

from hacheck import checker
from hacheck import config
from hacheck import spool

se = mock.sentinel


def bind_synchronous_unused_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    return s, port


class ReturnTwoHundred(tornado.web.RequestHandler):
    def get(self):
        self.write(b'TEST OK')


class ExpectServiceNameHeader(tornado.web.RequestHandler):
    def get(self):
        self.write(self.request.headers['SName'])


class ReturnFiveOhOne(tornado.web.RequestHandler):
    def get(self):
        self.set_status(501)
        self.write(b'NOPE')


class EchoParamFoo(tornado.web.RequestHandler):
    def get(self):
        self.write(self.get_argument('foo'))


class TestChecker(TestCase):
    def test_spool_success(self):
        with mock.patch.object(spool, 'is_up', return_value=(True, {})):
            fut = checker.check_spool(se.name, se.port, se.query, None, query_params=None, headers={})
            self.assertIsInstance(fut, tornado.concurrent.Future)
            self.assertTrue(fut.done())
            res = fut.result()
            self.assertEqual(res[0], 200)

    def test_spool_failure(self):
        with mock.patch.object(spool, 'is_up', return_value=(False, {'service': se.service})):
            fut = checker.check_spool(se.name, se.port, se.query, None, query_params=None, headers={})
            self.assertEqual(fut.result()[0], 503)


class ValidHaproxyResponse(tornado.web.RequestHandler):
    def get(self):
        self.set_status(200)
        self.write('''# pxname,svname,qcur,qmax,scur,smax,slim,stot,bin,bout,dreq,dresp,ereq,econ,eresp,wretr,wredis,status,weight,act,bck,chkfail,chkdown,lastchg,downtime,qlimit,pid,iid,sid,throttle,lbtot,tracked,type,rate,rate_lim,rate_max,check_status,check_code,check_duration,hrsp_1xx,hrsp_2xx,hrsp_3xx,hrsp_4xx,hrsp_5xx,hrsp_other,hanafail,req_rate,req_rate_max,req_tot,cli_abrt,srv_abrt,comp_in,comp_out,comp_byp,comp_rsp,lastsess,last_chk,last_agt,qtime,ctime,rtime,ttime,
stats,FRONTEND,,,1,1,2000,48,4542,293789,0,0,0,,,,,OPEN,,,,,,,,,1,2,0,,,,0,1,0,1,,,,0,47,0,0,0,0,,1,1,48,,,0,0,0,0,,,,,,,,
stats,BACKEND,0,0,0,0,200,0,4542,293789,0,0,,0,0,0,0,UP,0,0,0,,0,709871,0,,1,2,0,,0,,1,0,,0,,,,0,0,0,0,0,0,,,,,0,0,0,0,0,0,0,,,0,0,1,1,
foofrontend,FRONTEND,,,0,0,2000,0,0,0,0,0,0,,,,,OPEN,,,,,,,,,1,4,0,,,,0,0,100,0,,,,0,0,0,0,0,0,,0,0,0,,,0,0,0,0,,,,,,,,
server1,localhost,0,0,0,0,,0,0,0,,0,,0,0,0,0,DOWN,100,1,0,1,1,709871,709871,,1,5,1,,0,,2,0,,0,L4CON,,0,0,0,0,0,0,0,0,,,,0,0,,,,,-1,Connection refused,,0,0,0,0,
downbackend,BACKEND,0,0,0,0,400,0,0,0,0,0,,0,0,0,0,DOWN,0,0,0,,1,709871,709871,,1,5,0,,0,,1,0,,0,,,,0,0,0,0,0,0,,,,,0,0,0,0,0,0,-1,,,0,0,0,0,
upbackend,BACKEND,0,0,0,0,400,0,0,0,0,0,,0,0,0,0,UP,0,0,0,,1,259589,259589,,1,14,0,,0,,1,0,,0,,,,0,0,0,0,0,0,,,,,0,0,0,0,0,0,-1,,,0,0,0,0,
postgres5503,FRONTEND,,,0,0,2000,0,0,0,0,0,0,,,,,OPEN,,,,,,,,,1,21,0,,,,0,0,0,0,,,,,,,,,,,0,0,0,,,0,0,0,0,,,,,,,,
postgres-soa-slave,localhost,0,0,0,0,,0,0,0,,0,,0,0,0,0,DOWN,10,1,0,2,2,259401,259435,,1,22,1,,0,,2,0,,0,L4CON,,0,,,,,,,0,,,,0,0,,,,,-1,Connection refused,,0,0,0,0,
postgres-soa-slave,BACKEND,0,0,0,0,200,0,0,0,0,0,,0,0,0,0,DOWN,0,0,0,,2,259401,259435,,1,22,0,,0,,1,0,,0,,,,,,,,,,,,,,0,0,0,0,0,0,-1,,,0,0,0,0,\n''')


class InvalidHaproxyResponse(tornado.web.RequestHandler):
    def get(self):
        self.set_status(500)


class ExceptionResponse(tornado.web.RequestHandler):
    def get(self):
        self.set_status(200)
        self.write('\x00\x00')


class TestHaproxyCheckerValidResponse(tornado.testing.AsyncHTTPTestCase):

    def get_app(self):
        return tornado.web.Application([
            ('/;csv', ValidHaproxyResponse),
        ])

    @tornado.testing.gen_test
    def test_downbackend(self):
        response = yield checker.check_haproxy("downbackend", self.get_http_port(), "/", io_loop=self.io_loop, query_params="", headers={})
        self.assertEqual((500, b'downbackend is DOWN'), response)

    @tornado.testing.gen_test
    def test_nonexistentbackend(self):
        response = yield checker.check_haproxy("nonexistentbackend", self.get_http_port(), "/", io_loop=self.io_loop, query_params="", headers={})
        self.assertEqual((500, b'nonexistentbackend is not found'), response)

    @tornado.testing.gen_test
    def test_upbackend(self):
        response = yield checker.check_haproxy("upbackend", self.get_http_port(), "/", io_loop=self.io_loop, query_params="", headers={})
        self.assertEqual((200, b'upbackend is UP'), response)


class TestHaproxyCheckerInvalidResponse(tornado.testing.AsyncHTTPTestCase):

    def get_app(self):
        return tornado.web.Application([
            ('/;csv', InvalidHaproxyResponse),
        ])

    @tornado.testing.gen_test
    def test_invalidhttpresponse(self):
        response = yield checker.check_haproxy("", self.get_http_port(), "/", io_loop=self.io_loop, query_params="", headers={})
        self.assertEqual((500, b''), response)


class TestHaproxyCheckerExceptionResponse(tornado.testing.AsyncHTTPTestCase):

    def get_app(self):
        return tornado.web.Application([
            ('/;csv', ExceptionResponse),
        ])

    @tornado.testing.gen_test
    def test_badresponse(self):
        port = self.get_http_port()
        response = yield checker.check_haproxy("", port, "/", io_loop=self.io_loop, query_params="", headers={})
        self.assertEqual(599, response[0])


class TestHTTPChecker(tornado.testing.AsyncHTTPTestCase):

    def get_app(self):
        return tornado.web.Application([
            ('/', ReturnTwoHundred),
            ('/sname', ExpectServiceNameHeader),
            ('/bip', ReturnFiveOhOne),
            ('/echo_foo', EchoParamFoo),
        ])

    @tornado.testing.gen_test
    def test_check_success(self):
        response = yield checker.check_http("foo", self.get_http_port(), "/", io_loop=self.io_loop, query_params="", headers={})
        self.assertEqual((200, b'TEST OK'), response)

    @tornado.testing.gen_test
    def test_check_failure(self):
        code, response = yield checker.check_http("foo", self.get_http_port(), "/bar", io_loop=self.io_loop, query_params="", headers={})
        self.assertEqual(404, code)

    @tornado.testing.gen_test
    def test_check_failure_with_code(self):
        code, response = yield checker.check_http("foo", self.get_http_port(), "/bip", io_loop=self.io_loop, query_params="", headers={})
        self.assertEqual(501, code)

    @tornado.testing.gen_test
    def test_check_wrong_port(self):
        code, response = yield checker.check_http("foo", self.get_http_port() + 1, "/", io_loop=self.io_loop, query_params="", headers={})
        self.assertEqual(599, code)

    @tornado.testing.gen_test
    def test_service_name_header(self):
        with mock.patch.dict(config.config, {'service_name_header': 'SName'}):
            code, response = yield checker.check_http('service_name', self.get_http_port(), "/sname", io_loop=self.io_loop, query_params="", headers={})
            self.assertEqual(b'service_name', response)

    @tornado.testing.gen_test
    def test_query_params_passed(self):
        response = yield checker.check_http("foo", self.get_http_port(), "/echo_foo", io_loop=self.io_loop, query_params="foo=bar", headers={})
        self.assertEqual((200, b'bar'), response)

    @tornado.testing.gen_test
    def test_query_params_not_passed(self):
        response = yield checker.check_http("foo", self.get_http_port(), "/echo_foo", io_loop=self.io_loop, query_params="", headers={})
        self.assertEqual(400, response[0])


class TestServer(tornado.tcpserver.TCPServer):
    def __init__(self, io_loop, response='hello\n'):
        self.response = response
        super(TestServer, self).__init__(io_loop=io_loop)

    @tornado.gen.coroutine
    def handle_stream(self, stream, address):
        yield stream.write(self.response)
        stream.close()


class TestTCPChecker(tornado.testing.AsyncTestCase):
    def setUp(self):
        super(TestTCPChecker, self).setUp()
        socket, port = tornado.testing.bind_unused_port()
        self.server = TestServer(io_loop=self.io_loop)
        self.server.add_socket(socket)
        self.socket = socket
        self.port = port
        unlistened_socket, unlistened_port = bind_synchronous_unused_port()
        self.unlistened_socket = unlistened_socket
        self.unlistened_port = unlistened_port

    def tearDown(self):
        super(TestTCPChecker, self).tearDown()
        try:
            self.server.stop()
            self.socket.close()
        except Exception:
            pass

    @tornado.testing.gen_test
    def test_check_success(self):
        response = yield checker.check_tcp("foo", self.port, None, io_loop=self.io_loop, query_params="", headers={})
        self.assertEqual(200, response[0])

    @tornado.testing.gen_test
    def test_check_failure(self):
        with mock.patch.object(checker, 'TIMEOUT', 1):
            response = yield checker.check_tcp("foo", self.unlistened_port, None, io_loop=self.io_loop, query_params="", headers={})
            self.assertEqual(response[0], 503)


class TestRedisSentinelChecker(tornado.testing.AsyncTestCase):
    def setUp(self):
        super(TestRedisSentinelChecker, self).setUp()
        socket, port = tornado.testing.bind_unused_port()
        self.server = TestServer(io_loop=self.io_loop)
        self.server.add_socket(socket)
        self.socket = socket
        self.port = port
        unlistened_socket, unlistened_port = bind_synchronous_unused_port()
        self.unlistened_socket = unlistened_socket
        self.unlistened_port = unlistened_port

    def tearDown(self):
        super(TestRedisSentinelChecker, self).tearDown()
        try:
            self.server.stop()
            self.socket.close()
        except Exception:
            pass

    @tornado.testing.gen_test
    def test_check_success(self):
        with mock.patch.object(self.server, 'response', b'+PONG\r\n'):
            response = yield checker.check_redis_sentinel("foo", self.port, None, io_loop=self.io_loop, query_params="", headers={})
            self.assertEqual(200, response[0], response[1])

    @tornado.testing.gen_test
    def test_check_error(self):
        with mock.patch.object(self.server, 'response', b'WAT\r\n'):
            response = yield checker.check_redis_sentinel("foo", self.port, None, io_loop=self.io_loop, query_params="", headers={})
            self.assertEqual(500, response[0])

    @tornado.testing.gen_test
    def test_check_timeout(self):
        with mock.patch.object(checker, 'TIMEOUT', 1):
            response = yield checker.check_tcp("foo", self.unlistened_port, None, io_loop=self.io_loop, query_params="", headers={})
            self.assertEqual(response[0], 503)
