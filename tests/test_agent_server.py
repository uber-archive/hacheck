import os

from hacheck import agent_server
from hacheck import spool

import six
import mock
import tornado.concurrent
import tornado.testing


class StringIOStream(tornado.iostream.BaseIOStream):
    def __init__(self, *args, **kwargs):
        super(StringIOStream, self).__init__(*args, **kwargs)
        # data from the server to the client
        self.server_data = six.BytesIO()
        # data from the client to the server
        self.client_data = six.BytesIO()

        self.client_offset_into_server_data = 0

    def set_server_data(self, data):
        self.server_data.write(data)

    def get_client_data(self):
        d = self.client_data.getvalue()
        self.client_data = six.BytesIO()
        return d

    def read_until(self, delimiter):
        rv = tornado.concurrent.Future()
        response = six.BytesIO()
        success = False
        self.server_data.seek(self.client_offset_into_server_data)
        while True:
            c = self.server_data.read(1)
            if not c:
                break
            response.write(c)
            if c == delimiter:
                rv.set_result(response.getvalue())
                success = True
                break
        if success:
            self.client_offset_info_server_data = self.server_data.tell()
        self.server_data.seek(0, 2)
        return rv

    def write(self, data):
        rv = tornado.concurrent.Future()
        rv.set_result(None)
        self.client_data.write(data)
        return rv

    def close(self):
        pass


class AgentServerTestCase(tornado.testing.AsyncTestCase):
    def setUp(self):
        super(AgentServerTestCase, self).setUp()
        self.server = agent_server.AgentServer(io_loop=self.io_loop)

    @tornado.testing.gen_test
    def test_basic_up(self):
        with mock.patch.object(spool, 'is_up', return_value=(True, {})):
            stream = StringIOStream()
            stream.set_server_data(b'server\n')
            yield self.server.handle_stream(stream, None)
            response = stream.get_client_data()
            self.assertEqual(response, b'up\n')

    @tornado.testing.gen_test
    def test_basic_down(self):
        with mock.patch.object(spool, 'is_up', return_value=(False, {'nope'})):
            stream = StringIOStream()
            stream.set_server_data(b'server\n')
            yield self.server.handle_stream(stream, None)
            response = stream.get_client_data()
            self.assertEqual(response, b'maint\n')
