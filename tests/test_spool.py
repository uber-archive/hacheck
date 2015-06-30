import os.path
import mock
import shutil
import tempfile
from unittest import TestCase

from hacheck import spool

se = mock.sentinel


class TestSpool(TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        spool.configure(self.root)

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_configure_creates_root(self):
        spool.configure(os.path.join(self.root, 'spool'))
        assert os.path.exists, 'spool'

    def test_configure_no_write(self):
        new_root = os.path.join(self.root, 'non_writable')
        os.mkdir(new_root)
        os.chmod(new_root, 0o555)
        self.assertRaises(ValueError, spool.configure, new_root, needs_write=True)

    def test_configure_no_write_no_needs_write(self):
        new_root = os.path.join(self.root, 'non_writable')
        os.mkdir(new_root)
        os.chmod(new_root, 0o555)
        spool.configure(new_root, needs_write=False)

    def test_basic(self):
        svcname = 'test_basic'
        self.assertEquals(True, spool.status(svcname)[0])
        self.assertEquals(True, spool.status(svcname, 1234)[0])
        spool.down(svcname, port=1234)
        self.assertEquals(True, spool.status(svcname)[0])
        self.assertEquals(False, spool.status(svcname, 1234)[0])
        spool.down(svcname)
        self.assertEquals(False, spool.status(svcname)[0])
        self.assertEquals(False, spool.is_up(svcname)[0])
        spool.up(svcname, port=1234)
        self.assertEquals(True, spool.status(svcname, 1234)[0])
        spool.up(svcname)
        self.assertEquals(True, spool.status(svcname)[0])

    def test_all(self):
        svcname = 'test_all'
        self.assertEquals(True, spool.status(svcname)[0])
        spool.down('all')
        self.assertEquals(True, spool.status(svcname)[0])
        self.assertEquals(False, spool.is_up(svcname)[0])

    def test_status_all_down(self):
        self.assertEqual(len(list(spool.status_all_down())), 0)
        spool.down('foo')
        self.assertEqual(
            list(spool.status_all_down()),
            [('foo', {'service': 'foo', 'reason': '', 'expiration': None, 'creation': mock.ANY})]
        )

    def test_repeated_ups_works(self):
        spool.up('all')
        spool.up('all')

    def test_spool_file_path(self):
        self.assertEqual(os.path.join(self.root, 'foo:1234'), spool.spool_file_path("foo", port=1234))
        self.assertEqual(os.path.join(self.root, 'foo'), spool.spool_file_path("foo", None))

    def test_parse_spool_file_path(self):
        self.assertEqual(("foo", 1234), spool.parse_spool_file_path(spool.spool_file_path("foo", 1234)))

    def test_serialize_spool_file_contents(self):
        actual = spool.serialize_spool_file_contents("hi", expiration=12345, creation=54321)
        assert '"reason": "hi"' in actual
        assert '"expiration": 12345' in actual
        assert '"creation": 54321' in actual

    def test_deserialize_spool_file_contents_legacy(self):
        actual = spool.deserialize_spool_file_contents("this is a reason")
        self.assertEqual(actual, {"reason": "this is a reason", "expiration": None, "creation": None})

    def test_deserialize_spool_file_contents_new(self):
        actual = spool.deserialize_spool_file_contents('{"reason": "hi", "expiration": 12345, "creation": 12344}')
        self.assertEqual(actual, {"reason": "hi", "expiration": 12345, "creation": 12344})

    def test_status_creation(self):
        now = 1000
        svcname = 'test_status_creation'

        with mock.patch('time.time', return_value=now):
            spool.down(svcname)
            up, info_dict = spool.status(svcname)
            spool.up(svcname)

        self.assertEqual(info_dict['creation'], 1000)

    def test_status_expiration(self):
        svcname = 'test_status_expiration'
        now = 1000
        future = now + 10
        past = now - 10

        with mock.patch('time.time', return_value=now):
            self.assertEquals(True, spool.status(svcname)[0])

            # First, check with expiration in future; everything should behave normally.
            spool.down(svcname, expiration=future)
            self.assertEquals(False, spool.status(svcname)[0])

            # Now, let's make sure we remove the spool file if its expiration is in the past.
            spool.down(svcname, expiration=past)
            self.assertEquals(True, os.path.exists(spool.spool_file_path(svcname, None)))

            self.assertEquals(True, spool.status(svcname)[0])
            self.assertEquals(False, os.path.exists(spool.spool_file_path(svcname, None)))
