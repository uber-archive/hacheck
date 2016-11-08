try:
    from unittest2 import TestCase
except ImportError:
    from unittest import TestCase

from hacheck import mysql


class TestMySQLHelpers(TestCase):
    def test_sxor(self):
        self.assertEqual(b'\0\0', mysql._sxor(b'00', b'00'))
        self.assertEqual(b'\f\f', mysql._sxor(b'\f\f', b'\0\0'))
        self.assertEqual(b'\f\f', mysql._sxor(b'\0\0', b'\f\f'))
        self.assertEqual(b'\0\0', mysql._sxor(b'\f\f', b'\f\f'))
        self.assertEqual(b'\x1f\x0a\x1e\x00\x0b', mysql._sxor(b'hello', b'world'))

    def test_lenc(self):
        self.assertEqual((1, 1), mysql._read_lenc(b'\x01'))
        self.assertEqual((255, 3), mysql._read_lenc(b'\xfc\xff\x00'))
        self.assertEqual((16777215, 4), mysql._read_lenc(b'\xfd\xff\xff\xff'))
        self.assertEqual((4294967295, 9), mysql._read_lenc(b'\xfe\xff\xff\xff\xff\x00\x00\x00\x00'))

    def test_password_hash(self):
        self.assertEqual(
            b'\x19W\xdc\xe2rB\x82\xe0\x18\xf4\r\x90X$\xcbca\xf8\x8dA',
            mysql._stupid_hash_password('12345678901234567890', 'password')
        )


# TODO: Write unit tests of the actual protocol
