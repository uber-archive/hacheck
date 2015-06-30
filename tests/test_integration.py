# test the whole shebang

import tempfile
import shutil

import mock
import tornado.testing
import tornado.web

import hacheck.cache
import hacheck.main
import hacheck.spool


class PingHandler(tornado.web.RequestHandler):
    response_message = b'PONG'
    succeed = True

    def get(self):
        if self.succeed:
            self.write(self.response_message)
        else:
            self.set_status(503)
            self.write(b'FAIL')


class ArgBarHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(self.get_argument('bar'))


class TestIntegration(tornado.testing.AsyncHTTPTestCase):
    def setUp(self):
        self.cwd = tempfile.mkdtemp()
        hacheck.spool.configure(spool_root=self.cwd)
        hacheck.cache.configure()
        super(TestIntegration, self).setUp()

    def tearDown(self):
        if self.cwd:
            shutil.rmtree(self.cwd)
        super(TestIntegration, self).tearDown()

    def get_app(self):
        hacheck_app = hacheck.main.get_app()
        hacheck_app.add_handlers(r'.*', [
            (r'/pinged', PingHandler),
            (r'/arg_bar', ArgBarHandler),
        ])
        return hacheck_app

    def test_selfie(self):
        response = self.fetch('/http/self/%d/status' % self.get_http_port())
        self.assertEqual(200, response.code)

    def test_ping(self):
        response = self.fetch('/http/test_app/%d/pinged' % self.get_http_port())
        self.assertEqual(200, response.code)
        self.assertEqual(b'PONG', response.body)

    def test_ping_fail(self):
        with mock.patch.object(PingHandler, 'succeed', False):
            response = self.fetch('/http/test_app/%d/pinged' % self.get_http_port())
            self.assertEqual(503, response.code)
            self.assertEqual(b'FAIL', response.body)

    def test_down_and_up(self):
        hacheck.spool.down('test_app', 'TESTING')
        response = self.fetch('/http/test_app/%d/pinged' % self.get_http_port())
        self.assertEqual(503, response.code)
        self.assertRegexpMatches(response.body, b'^Service test_app in down state since (\d|\.)*: TESTING$')
        hacheck.spool.up('test_app')
        response = self.fetch('/http/test_app/%d/pinged' % self.get_http_port())
        self.assertEqual(b'PONG', response.body)

    def test_caching(self):
        hacheck.spool.up('test_app')
        response = self.fetch('/http/test_app/%d/pinged' % self.get_http_port())
        self.assertEqual(200, response.code)
        self.assertEqual(b'PONG', response.body)
        with mock.patch.object(PingHandler, 'response_message', b'dinged'):
            # first fetch should return the cached value
            response = self.fetch('/http/test_app/%d/pinged' % self.get_http_port())
            self.assertEqual(200, response.code)
            self.assertEqual(b'PONG', response.body)
            # test that sending Pragma: no-cache overrides the cached value
            response = self.fetch('/http/test_app/%d/pinged' % self.get_http_port(), headers={'Pragma': 'no-cache'})
            self.assertEqual(200, response.code)
            self.assertEqual(b'dinged', response.body)
            # subsequent requests should have the cache busted
            response = self.fetch('/http/test_app/%d/pinged' % self.get_http_port())
            self.assertEqual(200, response.code)
            self.assertEqual(b'dinged', response.body)

    def test_query_parameters_bad(self):
        response = self.fetch('/http/test_app/%d/arg_bar' % self.get_http_port())
        self.assertEqual(400, response.code)

    def test_query_parameters_good(self):
        response = self.fetch('/http/test_app/%d/arg_bar?bar=baz' % self.get_http_port())
        self.assertEqual(200, response.code)
        self.assertEqual(b'baz', response.body)
