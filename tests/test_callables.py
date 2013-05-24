import contextlib

import mock
from unittest import TestCase

import hacheck.haupdown
import hacheck.spool


class TestCallable(TestCase):
    @contextlib.contextmanager
    def setup_wrapper(self, args=frozenset()):
        with mock.patch.object(hacheck, 'spool', return_value=(True, {})) as mock_spool,\
                mock.patch('sys.argv', ['ignored', 'service_name'] + list(args)):
            yield mock_spool

    def test_basic(self):
        with self.setup_wrapper() as spooler:
            spooler.status.return_value = (True, {})
            hacheck.haupdown.main()
            spooler.configure.assert_called_once_with('/var/spool/hacheck', needs_write=True)

    def test_exit_codes(self):
        with self.setup_wrapper() as spooler:
            spooler.status.return_value = (True, {})
            self.assertEqual(0, hacheck.haupdown.main())
            spooler.status.return_value = (False, {'reason': 'irrelevant'})
            self.assertEqual(1, hacheck.haupdown.main())

    def test_up(self):
        with self.setup_wrapper() as spooler:
            hacheck.haupdown.up()
            spooler.up.assert_called_once_with('service_name')

    def test_down(self):
        with self.setup_wrapper() as spooler:
            hacheck.haupdown.down()
            spooler.down.assert_called_once_with('service_name', '')

    def test_down_with_reason(self):
        with self.setup_wrapper(['-r', 'something']) as spooler:
            hacheck.haupdown.down()
            spooler.down.assert_called_once_with('service_name', 'something')

    def test_status(self):
        with self.setup_wrapper() as spooler:
            spooler.status.return_value = (True, {})
            hacheck.haupdown.status()
            spooler.status.assert_called_once_with('service_name')
