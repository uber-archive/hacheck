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
        with mock.patch.object(spool, 'is_up', return_value=(True, {})) as is_up_patch:
            fut = checker.check_spool(se.name, se.port, se.query, None, query_params=None, headers={})
            self.assertIsInstance(fut, tornado.concurrent.Future)
            self.assertTrue(fut.done())
            res = fut.result()
            self.assertEqual(res[0], 200)
            is_up_patch.assert_called_once_with(se.name, port=se.port)

    def test_spool_failure(self):
        with mock.patch.object(spool, 'is_up', return_value=(False, {'service': se.service})) as is_up_patch:
            fut = checker.check_spool(se.name, se.port, se.query, None, query_params=None, headers={})
            self.assertEqual(fut.result()[0], 503)
            is_up_patch.assert_called_once_with(se.name, port=se.port)


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
        response = yield checker.check_http("foo", self.get_http_port(), "/", io_loop=self.io_loop, query_params="",
                                            headers={})
        self.assertEqual((200, b'TEST OK'), response)

    @tornado.testing.gen_test
    def test_check_failure(self):
        code, response = yield checker.check_http("foo", self.get_http_port(), "/bar", io_loop=self.io_loop,
                                                  query_params="", headers={})
        self.assertEqual(404, code)

    @tornado.testing.gen_test
    def test_check_failure_with_code(self):
        code, response = yield checker.check_http("foo", self.get_http_port(), "/bip", io_loop=self.io_loop,
                                                  query_params="", headers={})
        self.assertEqual(501, code)

    @tornado.testing.gen_test
    def test_check_wrong_port(self):
        code, response = yield checker.check_http("foo", self.get_http_port() + 1, "/", io_loop=self.io_loop,
                                                  query_params="", headers={})
        self.assertEqual(599, code)

    @tornado.testing.gen_test
    def test_service_name_header(self):
        with mock.patch.dict(config.config, {'service_name_header': 'SName'}):
            code, response = yield checker.check_http('service_name', self.get_http_port(), "/sname",
                                                      io_loop=self.io_loop, query_params="", headers={})
            self.assertEqual(b'service_name', response)

    @tornado.testing.gen_test
    def test_query_params_passed(self):
        response = yield checker.check_http("foo", self.get_http_port(), "/echo_foo", io_loop=self.io_loop,
                                            query_params="foo=bar", headers={})
        self.assertEqual((200, b'bar'), response)

    @tornado.testing.gen_test
    def test_query_params_not_passed(self):
        response = yield checker.check_http("foo", self.get_http_port(), "/echo_foo", io_loop=self.io_loop,
                                            query_params="", headers={})
        self.assertEqual(400, response[0])


class TestServer(tornado.tcpserver.TCPServer):
    @tornado.gen.coroutine
    def handle_stream(stream):
        yield stream.write('hello')
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
            response = yield checker.check_tcp("foo", self.unlistened_port, None, io_loop=self.io_loop, query_params="",
                                               headers={})
            self.assertEqual(response[0], 503)
