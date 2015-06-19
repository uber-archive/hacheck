import contextlib
from hacheck.compat import nested

import mock
import json
import os
from unittest import TestCase

import hacheck.haupdown
import hacheck.spool

# can't use an actual mock.sentinel because it doesn't support string ops
sentinel_service_name = 'testing_service_name'


class TestCallable(TestCase):
    @contextlib.contextmanager
    def setup_wrapper(self, args=frozenset()):
        with nested(
                mock.patch.object(hacheck, 'spool', return_value=(True, {})),
                mock.patch.object(hacheck.haupdown, 'print_s'),
                mock.patch('sys.argv', ['ignored'] + list(args))
        ) as (mock_spool, mock_print, _1):
            yield mock_spool, mock_print

    def test_basic(self):
        with self.setup_wrapper() as (spooler, _):
            spooler.status.return_value = (True, {})
            hacheck.haupdown.main('status_downed')
            spooler.configure.assert_called_once_with('/var/spool/hacheck', needs_write=False)

    def test_exit_codes(self):
        with self.setup_wrapper([sentinel_service_name]) as (spooler, mock_print):
            spooler.status.return_value = (True, {})
            self.assertEqual(0, hacheck.haupdown.main('status'))
            mock_print.assert_any_call('UP\t%s', sentinel_service_name)
            spooler.status.return_value = (False, {'reason': 'irrelevant'})
            self.assertEqual(1, hacheck.haupdown.main('status'))
            mock_print.assert_any_call('DOWN\t%f\t%s\t%s', float('Inf'), sentinel_service_name, 'irrelevant')

    def test_up(self):
        with self.setup_wrapper([sentinel_service_name]) as (spooler, mock_print):
            hacheck.haupdown.up()
            spooler.up.assert_called_once_with(sentinel_service_name, port=None)
            self.assertEqual(mock_print.call_count, 0)

    def test_up_with_port(self):
        with self.setup_wrapper(['-P', '1234', sentinel_service_name]) as (spooler, mock_print):
            hacheck.haupdown.up()
            spooler.up.assert_called_once_with(sentinel_service_name, port=1234)
            self.assertEqual(mock_print.call_count, 0)

    def test_down(self):
        os.environ['SSH_USER'] = 'testyuser'
        os.environ['SUDO_USER'] = 'testyuser'
        with self.setup_wrapper([sentinel_service_name]) as (spooler, mock_print):
            hacheck.haupdown.down()
            spooler.down.assert_called_once_with(sentinel_service_name, 'testyuser', expiration=None, port=None)
            self.assertEqual(mock_print.call_count, 0)

    def test_down_with_reason(self):
        with self.setup_wrapper(['-r', 'something', sentinel_service_name]) as (spooler, mock_print):
            hacheck.haupdown.down()
            spooler.down.assert_called_once_with(sentinel_service_name, 'something', expiration=None, port=None)
            self.assertEqual(mock_print.call_count, 0)

    def test_down_with_expiration(self):
        with self.setup_wrapper(['-e', '9876543210', sentinel_service_name]) as (spooler, mock_print):
            hacheck.haupdown.down()
            spooler.down.assert_called_once_with(sentinel_service_name, 'testyuser', expiration=9876543210, port=None)
            self.assertEqual(mock_print.call_count, 0)

    def test_down_with_port(self):
        with self.setup_wrapper(['-P', '1234', sentinel_service_name]) as (spooler, mock_print):
            hacheck.haupdown.down()
            spooler.down.assert_called_once_with(sentinel_service_name, 'testyuser', expiration=None, port=1234)
            self.assertEqual(mock_print.call_count, 0)

    def test_status(self):
        with self.setup_wrapper([sentinel_service_name]) as (spooler, mock_print):
            spooler.status.return_value = (True, {})
            hacheck.haupdown.status()
            spooler.status.assert_called_once_with(sentinel_service_name)
            mock_print.assert_called_once_with("UP\t%s", sentinel_service_name)

    def test_status_downed(self):
        with self.setup_wrapper() as (spooler, mock_print):
            spooler.status_all_down.return_value = [
                (sentinel_service_name, {'service': sentinel_service_name, 'reason': '', 'expiration': None})
            ]
            self.assertEqual(hacheck.haupdown.status_downed(), 0)
            mock_print.assert_called_once_with("DOWN\t%f\t%s\t%s", float('Inf'), sentinel_service_name, mock.ANY)

    def test_status_downed_expiration(self):
        with self.setup_wrapper() as (spooler, mock_print):
            spooler.status_all_down.return_value = [
                (sentinel_service_name, {'service': sentinel_service_name, 'reason': '', 'expiration': 9876543210})
            ]
            self.assertEqual(hacheck.haupdown.status_downed(), 0)
            mock_print.assert_called_once_with("DOWN\t%f\t%s\t%s", 9876543210, sentinel_service_name, mock.ANY)

    def test_list(self):
        with self.setup_wrapper() as (spooler, mock_print):
            with mock.patch.object(hacheck.haupdown, 'urlopen') as mock_urlopen:
                mock_urlopen.return_value.read.return_value = json.dumps({
                    "seen_services": ["foo"],
                    "threshold_seconds": 10,
                })
                self.assertEqual(hacheck.haupdown.halist(), 0)
                mock_urlopen.assert_called_once_with('http://127.0.0.1:3333/recent', timeout=mock.ANY)
                mock_print.assert_called_once_with("foo")
