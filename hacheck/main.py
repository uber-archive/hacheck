import optparse
import time

import tornado.ioloop
import tornado.web

from . import cache
from . import handlers
from . import spool


def main():
    parser = optparse.OptionParser()
    parser.add_option('-p', '--port', default=3333, type=int)
    parser.add_option('--cache-time', default=10.0, type=float,
            help='How many seconds to cache response for (default %default)')
    parser.add_option('--spool-root', default='/var/spool/hastate',
            help='Root for spool for service states (default %default)')
    opts, args = parser.parse_args()
    ioloop = tornado.ioloop.IOLoop.instance()
    application = tornado.web.Application([
        (r'/([a-zA-Z0-9]+)/([0-9]+)/(.*)', handlers.ServiceHandler),
        (r'/status', handlers.StatusHandler),
    ], start_time=time.time())
    cache.configure(cache_time=opts.cache_time)
    spool.configure(spool_root=opts.spool_root)
    application.listen(opts.port)
    ioloop.start()


if __name__ == '__main__':
    main()
