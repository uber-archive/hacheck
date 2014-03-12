import logging
import optparse
import signal
import time
import sys

import tornado.ioloop
import tornado.web

from . import cache
from . import config
from . import handlers
from . import spool


def get_app():
    return tornado.web.Application([
        (r'/http/([a-zA-Z0-9_-]+)/([0-9]+)/(.*)', handlers.HTTPServiceHandler),
        (r'/tcp/([a-zA-Z0-9_-]+)/([0-9]+)/?(.*)', handlers.TCPServiceHandler),
        (r'/spool/([a-zA-Z0-9_-]+)/([0-9]+)/?(.*)', handlers.SpoolServiceHandler),
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
        default=3333,
        type=int
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
    log_kwargs = {
        'level': logging.DEBUG if opts.verbose else logging.WARNING,
    }
    if config.config['log_path'] == 'stdout':
        log_kwargs['stream'] = sys.stdout
    elif config.config['log_path'] == 'stderr':
        log_kwargs['stream'] = sys.stderr
    else:
        log_kwargs['filename'] = config.config['log_path']
    logging.basicConfig(**log_kwargs)
    cache.configure(cache_time=config.config['cache_time'])
    spool.configure(spool_root=opts.spool_root)
    application = get_app()
    application.listen(opts.port)
    ioloop = tornado.ioloop.IOLoop.instance()
    for sig in (signal.SIGTERM, signal.SIGQUIT, signal.SIGINT):
        signal.signal(sig, lambda *args: ioloop.stop())
    ioloop.start()
    return 0


if __name__ == '__main__':
    sys.exit(main())
