"""clean-room implementation of a mysql client supporting both *connect* and *quit* operations"""

import datetime
import socket
import struct
import sys
import time
from hashlib import sha1

from . import compat

import tornado.gen
import tornado.iostream


def _sxor(lhs, rhs):
    if sys.version_info > (3, 0):
        return b''.join(compat.bchr(a ^ b) for a, b in zip(lhs, rhs))
    else:
        return b''.join(compat.bchr(ord(a) ^ ord(b)) for a, b in zip(lhs, rhs))


def _stupid_hash_password(salt, password):
    password = password.encode('utf-8')
    salt = salt.encode('utf-8')
    return _sxor(
        sha1(password).digest(),
        sha1(
            salt + sha1(sha1(password).digest()).digest()
        ).digest()
    )


def _read_lenc(buf, offset=0):
    first = struct.unpack('B', buf[offset:offset + 1])[0]
    if first < 0xfb:
        return first, offset + 1
    elif first == 0xfc:
        return struct.unpack('<H', buf[offset + 1:offset + 3])[0], offset + 3
    elif first == 0xfd:
        return struct.unpack('<I', buf[offset + 1:offset + 4] + b'\0')[0], offset + 4
    elif first == 0xfe:
        return struct.unpack('<Q', buf[offset + 1:offset + 9])[0], offset + 9


class MySQLResponse(object):
    def __init__(self, packet_contents):
        self.packet = packet_contents
        self.header = struct.unpack('B', packet_contents[0])[0]
        self.message = ''

        # per-type response parsing
        if self.header == 0x00:
            self.response_type = 'OK'
            offset = 1
            self.rows_affected, offset = _read_lenc(packet_contents, offset)
            self.last_insert_id, offset = _read_lenc(packet_contents, offset)
            self.status_flags, self.warnings = struct.unpack('<HH', packet_contents[offset:offset + 4])
            self.message = packet_contents[offset + 4:]
        elif self.header == 0x0a:
            self.response_type = 'CONN 10'
            sve = packet_contents.index('\0')
            self.server_version = packet_contents[1:sve]
            sve += 1
            self.connection_id, pd_low, cf_low = struct.unpack(
                '<I8sx2s',
                packet_contents[sve:sve + 15]
            )
            self.character_set, self.status_flags, cf_high = struct.unpack(
                'BH2s',
                packet_contents[sve + 15:sve + 21]
            )
            self.capability_flags = struct.unpack('<I', cf_low + cf_high)[0]
            pd_len = struct.unpack('B', packet_contents[sve + 20:sve + 21])[0]
            # skip 10 bytes for REASONS
            pd_end = sve + 31 + max(13, pd_len - 8)
            pd_high = packet_contents[sve + 31:pd_end - 1]
            self.plugin_data = pd_low + pd_high
            self.auth_method = packet_contents[pd_end:-1]
        elif self.header == 0xfe:
            self.response_type = 'EOF'
        elif self.header == 0xff:
            self.response_type = 'ERR'
            self.error_code, _, self.sql_state = struct.unpack(
                'Hc5s',
                packet_contents[1:9]
            )
            self.message = packet_contents[9:]
        else:
            self.response_type = self.header

        if self.header > 0xf0:
            self.OK = False
        else:
            self.OK = True

    def __repr__(self):
        return '%s(%s)<%s>' % (self.__class__.__name__, self.response_type, self.message)


class MySQLClient(object):
    def __init__(self, host='127.0.0.1', port=3306, global_timeout=0, io_loop=None, timeout_callback=None):
        self.host = host
        self.port = port
        self.global_timeout = global_timeout
        self.timeout_callback = timeout_callback
        if io_loop is None:
            io_loop = tornado.ioloop.IOLoop.current()
        self.io_loop = io_loop
        self.socket = None
        self.stream = None
        self.start = 0
        self.timeout = None
        self.connected = False
        self.sequence = 1

    @tornado.gen.coroutine
    def _connect_socket(self):
        self.start = time.time()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.stream = tornado.iostream.IOStream(s, io_loop=self.io_loop)
        if self.global_timeout:
            self.timeout = self.io_loop.add_timeout(datetime.timedelta(seconds=self.global_timeout), self._timed_out)
        yield tornado.gen.Task(self.stream.connect, (self.host, self.port))
        self.connected = True

    def _timed_out(self):
        now = time.time()
        try:
            self.stream.close()
        except Exception:
            pass
        if self.timeout_callback is not None:
            self.timeout_callback(now - self.start)

    @tornado.gen.coroutine
    def connect(self, username, password):
        yield self._connect_socket()
        connection_response = yield self.read_response()
        assert connection_response.header == 0x0a
        connection_packet = struct.pack(
            '<IIB23x',
            0x200 | 0x400 | 0x8000 | 0x80000,  # connection flags
            1024,  # max packet size
            0x21,  # char set == utf8
        )
        connection_packet += username.encode('utf8') + '\0'
        auth_response = _stupid_hash_password(password=password, salt=connection_response.plugin_data)
        connection_packet += struct.pack('B', len(auth_response))
        connection_packet += auth_response
        connection_packet += 'mysql_native_password\0'
        yield self.write(self._pack_packet(connection_packet))
        resp = yield self.read_response()
        raise tornado.gen.Return(resp)

    def _pack_packet(self, contents):
        size = len(contents)
        packet_size = struct.pack('<i', size)[:3]
        sequence_number = struct.pack('B', self.sequence)
        self.sequence += 1
        packet = packet_size + sequence_number + contents
        return packet

    def write(self, bytez):
        return tornado.gen.Task(self.stream.write, bytez)

    def read_bytes(self, byte_count):
        return tornado.gen.Task(self.stream.read_bytes, byte_count)

    @tornado.gen.coroutine
    def quit(self):
        assert self.connected
        packet_contents = struct.pack('B', 0x01)
        self.sequence = 0
        yield self.write(self._pack_packet(packet_contents))
        try:
            self.stream.close()
        except Exception:
            pass

    @tornado.gen.coroutine
    def read_response(self):
        packet_length = yield self.read_bytes(3)
        packet_length = struct.unpack('<I', packet_length + struct.pack('B', 0x00))[0]
        sequence_number = yield self.read_bytes(1)
        sequence_number = struct.unpack('B', sequence_number)[0]
        packet = yield self.read_bytes(packet_length)
        raise tornado.gen.Return(MySQLResponse(packet))
