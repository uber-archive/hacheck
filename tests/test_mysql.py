import mock
try:
    from unittest2 import TestCase
except ImportError:
    from unittest import TestCase

import tornado.concurrent
import tornado.web
import tornado.testing

from hacheck import mysql


class TestMySQLHelpers(TestCase):
    def test_sxor(self):
        self.assertEqual('\0\0', mysql._sxor('00', '00'))
        self.assertEqual('\f\f', mysql._sxor('\f\f', '\0\0'))
        self.assertEqual('\f\f', mysql._sxor('\0\0', '\f\f'))
        self.assertEqual('\0\0', mysql._sxor('\f\f', '\f\f'))
        self.assertEqual('\x1f\x0a\x1e\x00\x0b', mysql._sxor('hello', 'world'))

    def test_lenc(self):
        self.assertEqual((1, 1), mysql._read_lenc('\x01'))
        self.assertEqual((255, 3), mysql._read_lenc('\xfc\xff\x00'))
        self.assertEqual((16777215, 4), mysql._read_lenc('\xfd\xff\xff\xff'))
        self.assertEqual((4294967295, 9), mysql._read_lenc('\xfe\xff\xff\xff\xff\x00\x00\x00\x00'))

    def test_password_hash(self):
        self.assertEqual(
            '\x19W\xdc\xe2rB\x82\xe0\x18\xf4\r\x90X$\xcbca\xf8\x8dA',
            mysql._stupid_hash_password('12345678901234567890', 'password')
        )


# TODO: Write unit tests of the actual protocol
