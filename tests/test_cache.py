import time
import mock

from unittest import TestCase

from hacheck import cache

se = mock.sentinel


class CacheTestCase(TestCase):
    def setUp(self):
        cache.configure()

    def test_expiry(self):
        with mock.patch.object(cache, 'has_expired', return_value=False) as m:
            cache.setv(se.key, se.value)
            self.assertEqual(cache.getv(se.key), se.value)
            self.assertEqual(m.call_count, 1)
        with mock.patch.object(cache, 'has_expired', return_value=True) as m:
            cache.setv(se.key, se.value)
            self.assertRaises(KeyError, cache.getv, se.key)
            self.assertEqual(m.call_count, 1)

    def test_configure(self):
        cache.configure(cache_time=13)
        with mock.patch('time.time', return_value=1):
            cache.setv(se.key, se.value)
            with mock.patch.object(cache, 'has_expired', return_value=False) as m:
                cache.getv(se.key, time.time())
                m.assert_called_once_with(cache.Record(14, mock.ANY), 1)

    def test_stats(self):
        with mock.patch.object(cache, 'has_expired', return_value=False):
            cache.setv(se.key, se.value)
            self.assertEqual(cache.get_stats()['sets'], 1)
            self.assertEqual(cache.get_stats()['gets'], 0)
            cache.getv(se.key)
            self.assertEqual(cache.get_stats()['gets'], 1)

    def test_stats_reset(self):
        self.assertEqual(cache.get_stats()['gets'], 0)
        self.assertRaises(KeyError, cache.getv, se.key)
        self.assertEqual(cache.get_stats()['gets'], 1)
        cache.configure()
        self.assertEqual(cache.get_stats()['gets'], 0)

    def test_has_expired(self):
        self.assertEqual(False, cache.has_expired(cache.Record(2, None), 1))
        self.assertEqual(True, cache.has_expired(cache.Record(1, None), 2))

    def test_busting(self):
        with mock.patch.object(cache, 'has_expired', return_value=False):
            cache.setv(se.key, se.value)
            with cache.maybe_bust(False):
                self.assertEqual(se.value, cache.getv(se.key))
            with cache.maybe_bust(True):
                self.assertRaises(KeyError, cache.getv, se.key)

    def test_decorator(self):
        @cache.cached
        def inner(arg):
            return arg()
        m = mock.Mock(return_value=se.rv)
        self.assertEqual(se.rv, inner(m))
        self.assertEqual(se.rv, inner(m))
        m.assert_called_once_with()

    def test_decorator_expiration(self):
        @cache.cached
        def inner(arg):
            return arg()
        m = mock.Mock(return_value=se.rv)
        with mock.patch.object(cache, 'has_expired', return_value=True):
            self.assertEqual(se.rv, inner(m))
            self.assertEqual(se.rv, inner(m))
            self.assertEqual(2, m.call_count)
