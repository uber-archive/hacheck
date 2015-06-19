import json
import tempfile
import shutil

from hacheck.compat import nested

import mock
import tornado.concurrent
import tornado.testing
import yaml

from hacheck import main
from hacheck import spool
from hacheck import cache
from hacheck import config
from hacheck import handlers


class ApplicationTestCase(tornado.testing.AsyncHTTPTestCase):
    def setUp(self):
        # flush the cache before every test
        cache.configure()
        self.config_file = tempfile.NamedTemporaryFile(delete=True)
        self.spool = tempfile.mkdtemp()
        mock_config = {
            'cache_time': 100.0,
            'spool_root': self.spool
        }
        self.config_file.write(yaml.dump(mock_config).encode('utf-8'))
        self.config_file.flush()
        spool.configure(spool_root=self.spool)
        handlers._reset_stats()
        super(ApplicationTestCase, self).setUp()

    def tearDown(self):
        if self.config_file:
            self.config_file.close()
        if self.spool:
            shutil.rmtree(self.spool)

    def get_app(self):
        return main.get_app()

    def test_status(self):
        response = self.fetch('/status')
        self.assertEqual('application/json; charset=UTF-8', response.headers['Content-Type'])
        result = json.loads(response.body.decode('utf-8'))
        self.assertGreater(result['uptime'], 0.0)

    def test_status_count(self):
        response = self.fetch('/status/count')
        self.assertEqual('application/json; charset=UTF-8', response.headers['Content-Type'])
        result = json.loads(response.body.decode('utf-8'))
        self.assertEqual(result['service_access_counts'], {})
        with mock.patch.object(spool, 'is_up', return_value=(True, {"reason": b'YES'})):
            response = self.fetch('/spool/foo/1/status')
            self.assertEqual(response.code, 200)
            self.assertEqual(response.body, b'YES')
        response = self.fetch('/status/count')
        result = json.loads(response.body.decode('utf-8'))
        self.assertEqual(result['service_access_counts'], {'foo': {'127.0.0.1': 1}})

    def test_routing(self):
        with mock.patch.object(handlers.HTTPServiceHandler, 'get') as m:
            self.fetch('/http/foo/1/status')
            m.assert_called_once_with('foo', '1', 'status')
        with mock.patch.object(handlers.TCPServiceHandler, 'get') as m:
            self.fetch('/tcp/bar/2')
            m.assert_called_once_with('bar', '2', '')

    def test_spool_checker(self):
        with mock.patch.object(spool, 'is_up', return_value=(True, {"reason": b'YES'})):
            response = self.fetch('/spool/foo/1/status')
            self.assertEqual(response.code, 200)
            self.assertEqual(response.body, b'YES')
        with mock.patch.object(spool, 'is_up', return_value=(False, {"service": "any", "reason": ""})):
            response = self.fetch('/spool/foo/1/status')
            self.assertEqual(response.code, 503)
            self.assertEqual(response.body, b'Service any in down state')
        with mock.patch.object(spool, 'is_up', return_value=(False, {"service": "any", "reason": "just because"})):
            response = self.fetch('/spool/foo/1/status')
            self.assertEqual(response.code, 503)
            self.assertEqual(response.body, b'Service any in down state: just because')

    def test_calls_all_checkers(self):
        rv1 = tornado.concurrent.Future()
        rv1.set_result((200, b'OK1'))
        rv2 = tornado.concurrent.Future()
        rv2.set_result((200, b'OK2'))
        checker1 = mock.Mock(return_value=rv1)
        checker2 = mock.Mock(return_value=rv2)
        with mock.patch.object(handlers.SpoolServiceHandler, 'CHECKERS', [checker1, checker2]):
            response = self.fetch('/spool/foo/1/status')
            self.assertEqual(200, response.code)
            self.assertEqual(b'OK2', response.body)
            checker1.assert_called_once_with('foo', 1, 'status', io_loop=mock.ANY, query_params='', headers=mock.ANY)
            checker2.assert_called_once_with('foo', 1, 'status', io_loop=mock.ANY, query_params='', headers=mock.ANY)

    def test_passes_headers(self):
        rv1 = tornado.concurrent.Future()
        rv1.set_result((200, b'OK1'))
        checker1 = mock.Mock(return_value=rv1)
        with mock.patch.object(handlers.SpoolServiceHandler, 'CHECKERS', [checker1]):
            response = self.fetch('/spool/foo/1/status')
            self.assertEqual(200, response.code)
            checker1.assert_called_with(
                'foo', 1, 'status', io_loop=mock.ANY, query_params='',
                headers={
                    'Connection': 'close',
                    'Host': mock.ANY,
                    'Accept-Encoding': 'gzip'
                },
            )

    def test_any_failure_fails_all_first(self):
        rv1 = tornado.concurrent.Future()
        rv1.set_result((404, b'NOK1'))
        rv2 = tornado.concurrent.Future()
        rv2.set_result((200, b'OK2'))
        checker1 = mock.Mock(return_value=rv1)
        checker2 = mock.Mock(return_value=rv2)
        with mock.patch.object(handlers.SpoolServiceHandler, 'CHECKERS', [checker1, checker2]):
            response = self.fetch('/spool/foo/2/status')
            self.assertEqual(404, response.code)
            self.assertEqual(b'NOK1', response.body)

    def test_any_failure_fails_all_second(self):
        rv1 = tornado.concurrent.Future()
        rv1.set_result((200, b'OK1'))
        rv2 = tornado.concurrent.Future()
        rv2.set_result((404, b'NOK2'))
        checker1 = mock.Mock(return_value=rv1)
        checker2 = mock.Mock(return_value=rv2)
        with mock.patch.object(handlers.SpoolServiceHandler, 'CHECKERS', [checker1, checker2]):
            response = self.fetch('/spool/foo/2/status')
            self.assertEqual(404, response.code)
            self.assertEqual(b'NOK2', response.body)

    def test_weird_code(self):
        # test that unusual HTTP codes are rewritten to 503s
        rv = tornado.concurrent.Future()
        rv.set_result((6000, 'this code is weird'))
        checker = mock.Mock(return_value=rv)
        with mock.patch.object(handlers.HTTPServiceHandler, 'CHECKERS', [checker]):
            response = self.fetch('/http/uncached-weird-code/80/status')
            self.assertEqual(503, response.code)

    def test_option_parsing(self):
        with nested(
            mock.patch('sys.argv', ['ignorethis', '-c', self.config_file.name, '--spool-root', 'foo']),
            mock.patch.object(tornado.ioloop.IOLoop, 'instance'),
            mock.patch.object(cache, 'configure'),
            mock.patch.object(main, 'get_app'),
            mock.patch.object(spool, 'configure')) \
                as (_1, _2, cache_configure, _3, spool_configure):
            main.main()
            spool_configure.assert_called_once_with(spool_root='foo')
            cache_configure.assert_called_once_with(cache_time=100)

    def test_show_recent(self):
        handlers.seen_services.clear()
        response = self.fetch('/spool/foo/1/status')
        self.assertEqual(200, response.code)
        response = self.fetch('/recent')
        b = json.loads(response.body.decode('utf-8'))
        self.assertEqual(
            b,
            {
                'seen_services': [['foo', {'code': 200, 'ts': mock.ANY, 'remote_ip': '127.0.0.1'}]],
                'threshold_seconds': 600
            })
        response = self.fetch('/recent?threshold=20')
        b = json.loads(response.body.decode('utf-8'))
        self.assertEqual(
            b,
            {
                'seen_services': [['foo', {'code': 200, 'ts': mock.ANY, 'remote_ip': '127.0.0.1'}]],
                'threshold_seconds': 20
            })

    def test_remote_spool_check_forbidden(self):
        with mock.patch.dict(config.config, {'allow_remote_spool_changes': False}):
            response = self.fetch('/spool/foo/1/status', method='POST', body="")
            self.assertEqual(response.code, 403)

    def test_spool_post(self):
        with nested(
            mock.patch.dict(config.config, {'allow_remote_spool_changes': True}),
            mock.patch.object(spool, 'up'),
            mock.patch.object(spool, 'down'),
                ) as (_1, spool_up, spool_down):

            response = self.fetch('/spool/foo/0/status', method='POST', body="status=up")
            self.assertEqual(response.code, 200)
            spool_up.assert_called_once_with('foo', port=None)

            response = self.fetch('/spool/foo/1234/status', method='POST', body="status=down&reason=because")
            self.assertEqual(response.code, 200)
            spool_down.assert_called_once_with('foo', reason='because', port=1234, expiration=None)

            spool_down.reset_mock()
            response = self.fetch('/spool/foo/1234/status', method='POST',
                                  body="status=down&reason=because&expiration=1")
            self.assertEqual(response.code, 200)
            spool_down.assert_called_once_with('foo', reason='because', port=1234, expiration=1)
