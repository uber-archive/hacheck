from . import spool

from tornado.gen import coroutine
from tornado.tcpserver import TCPServer


class AgentServer(TCPServer):
    def __init__(self, io_loop=None):
        super(AgentServer, self).__init__(io_loop=io_loop)

    @coroutine
    def handle_stream(self, stream, address):
        service_name = (yield stream.read_until(b'\n')).decode('utf-8').rstrip().split('/', 1)[0]
        up, extra_info = spool.is_up(service_name)
        if up:
            yield stream.write('ready\n'.encode('ascii'))
        else:
            yield stream.write('maint\n'.encode('ascii'))
        stream.close()
        return
