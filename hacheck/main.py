import logging
import optparse
import signal
import time
import sys

import tornado.ioloop
import tornado.httpserver
import tornado.web

from . import cache
from . import config
from . import handlers
from . import spool


def get_app():
    return tornado.web.Application([
        (r'/http/([a-zA-Z0-9_-]+)/([0-9]+)/(.*)', handlers.HTTPServiceHandler),
        (r'/tcp/([a-zA-Z0-9_-]+)/([0-9]+)/?(.*)', handlers.TCPServiceHandler),
        (r'/mysql/([a-zA-Z0-9_-]+)/([0-9]+)/?(.*)', handlers.MySQLServiceHandler),
        (r'/spool/([a-zA-Z0-9_-]+)/([0-9]+)/?(.*)', handlers.SpoolServiceHandler),
        (r'/recent', handlers.ListRecentHandler),
        (r'/status', handlers.StatusHandler),
    ], start_time=time.time())


def main():
    parser = optparse.OptionParser()
    parser.add_option(
        '-c',
        '--config-file',
        default=None,
        help='Path to a YAML config file'
    )
    parser.add_option(
        '-p',
        '--port',
        default=[],
        type=int,
        action='append',
        help='Port to listen on. May be repeated. If not passed, defaults to :3333.'
    )
    parser.add_option(
        '-B',
        '--bind-address',
        default='0.0.0.0',
        help='Address to listen on. Defaults to %default'
    )
    parser.add_option(
        '--spool-root',
        default='/var/spool/hacheck',
        help='Root for spool for service states (default %default)'
    )
    parser.add_option(
        '-v',
        '--verbose',
        default=False,
        action='store_true'
    )
    opts, args = parser.parse_args()
    if opts.config_file is not None:
        config.load_from(opts.config_file)

    if not opts.port:
        opts.port = [3333]

    # set up logging
    log_path = config.config['log_path']
    level = logging.DEBUG if opts.verbose else logging.WARNING
    if log_path == 'stdout':
        handler = logging.StreamHandler(sys.stdout)
    elif log_path == 'stderr':
        handler = logging.StreamHandler(sys.stderr)
    else:
        handler = logging.handlers.WatchedFileHandler(log_path)
    fmt = logging.Formatter(logging.BASIC_FORMAT, None)
    handler.setFormatter(fmt)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(level)

    # application stuff
    cache.configure(cache_time=config.config['cache_time'])
    spool.configure(spool_root=opts.spool_root)
    application = get_app()
    ioloop = tornado.ioloop.IOLoop.instance()
    server = tornado.httpserver.HTTPServer(application, io_loop=ioloop)
    for port in opts.port:
        server.listen(port, opts.bind_address)
    for sig in (signal.SIGTERM, signal.SIGQUIT, signal.SIGINT):
        signal.signal(sig, lambda *args: ioloop.stop())
    ioloop.start()
    return 0


if __name__ == '__main__':
    sys.exit(main())
