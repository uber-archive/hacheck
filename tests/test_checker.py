import mock
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


class TestChecker(TestCase):
    def test_spool_success(self):
        with mock.patch.object(spool, 'is_up', return_value=(True, {})):
            fut = checker.check_spool(se.name, se.port, se.query, None)
            self.assertIsInstance(fut, tornado.concurrent.Future)
            self.assertTrue(fut.done())
            res = fut.result()
            self.assertEqual(res[0], 200)

    def test_spool_failure(self):
        with mock.patch.object(spool, 'is_up', return_value=(False, {'service': se.service})):
            fut = checker.check_spool(se.name, se.port, se.query, None)
            self.assertEqual(fut.result()[0], 503)


class TestHTTPChecker(tornado.testing.AsyncHTTPTestCase):

    def get_app(self):
        return tornado.web.Application([
            ('/', ReturnTwoHundred),
            ('/sname', ExpectServiceNameHeader),
            ('/bip', ReturnFiveOhOne),
        ])

    def test_check_success(self):
        def success(fut):
            self.assertEqual((200, b'TEST OK'), fut.result())
            self.stop()
        future = checker.check_http("foo", self.get_http_port(), "/", io_loop=self.io_loop)
        future.add_done_callback(success)
        self.wait()

    def test_check_failure(self):
        def success(fut):
            self.assertEqual(404, fut.result()[0])
            self.stop()
        future = checker.check_http("foo", self.get_http_port(), "/bar", io_loop=self.io_loop)
        future.add_done_callback(success)
        self.wait()

    def test_check_failure_with_code(self):
        def success(fut):
            self.assertEqual(501, fut.result()[0])
            self.stop()
        future = checker.check_http("foo", self.get_http_port(), "/bip", io_loop=self.io_loop)
        future.add_done_callback(success)
        self.wait()

    def test_check_wrong_port(self):
        def success(fut):
            self.assertEqual(599, fut.result()[0])
            self.stop()
        future = checker.check_http("foo", self.get_http_port() + 1, "/", io_loop=self.io_loop)
        future.add_done_callback(success)
        self.wait()

    def test_service_name_header(self):
        def success(fut):
            self.assertEqual(b'service_name', fut.result()[1])
            self.stop()
        with mock.patch.dict(config.config, {'service_name_header': 'SName'}):
            future = checker.check_http('service_name', self.get_http_port(), "/sname", io_loop=self.io_loop)
            future.add_done_callback(success)
            self.wait()


class TestTCPChecker(tornado.testing.AsyncTestCase):
    def setUp(self):
        super(TestTCPChecker, self).setUp()
        socket, port = tornado.testing.bind_unused_port()
        self.server = tornado.tcpserver.TCPServer(io_loop=self.io_loop)
        self.server.add_socket(socket)
        self.socket = socket
        self.port = port

    def tearDown(self):
        super(TestTCPChecker, self).tearDown()
        self.server.stop()
        self.socket.close()

    def test_check_success(self):
        future = checker.check_tcp("foo", self.port, None, io_loop=self.io_loop)
        future.add_done_callback(self.stop)
        response = self.wait()
        self.assertEqual(response.result()[0], 200)

    def test_check_failure(self):
        with mock.patch.object(checker, 'TIMEOUT', 1):
            future = checker.check_tcp("foo", self.port + 1, None, io_loop=self.io_loop)
            future.add_done_callback(self.stop)
            response = self.wait()
            self.assertEqual(response.result()[0], 503)
