import resource
import mock

from unittest import TestCase

from hacheck import main


@mock.patch('resource.getrlimit', return_value=(10, 20))
@mock.patch('resource.setrlimit')
class SetRLimitNOFILETestCase(TestCase):
    def test_max(self, mock_setrlimit, mock_getrlimit):
        main.setrlimit_nofile('max')
        mock_setrlimit.assert_called_once_with(resource.RLIMIT_NOFILE, (20, 20))

    def test_specific(self, mock_setrlimit, mock_getrlimit):
        main.setrlimit_nofile(12)
        mock_setrlimit.assert_called_once_with(resource.RLIMIT_NOFILE, (12, 20))

    def test_illegal(self, mock_setrlimit, mock_getrlimit):
        self.assertRaises(ValueError, main.setrlimit_nofile, 25)
