#!/usr/bin/env python

import optparse
import sys

import hacheck.spool


def up():
    return main('up')


def down():
    return main('down')


def status():
    return main('status')


def main(default_action='status'):
    ACTIONS = ('up', 'down', 'status')
    parser = optparse.OptionParser(usage='%prog [options] service_name')
    parser.add_option('--spool-root', default='/var/spool/hacheck',
        help='Root for spool for service states (default %default)')
    parser.add_option('-a', '--action', type='choice', choices=ACTIONS, default=default_action,
        help='Action (one of %s, default %%default)' % ', '.join(ACTIONS, ))
    parser.add_option('-r', '--reason', type=str, default="", help='Reason string when setting down')
    opts, args = parser.parse_args()

    if len(args) != 1:
        parser.error('Wrong number of arguments')
    service_name = args[0]

    hacheck.spool.configure(opts.spool_root, needs_write=True)

    if opts.action == 'up':
        hacheck.spool.up(service_name)
        return 0
    elif opts.action == 'down':
        hacheck.spool.down(service_name, opts.reason)
        return 0
    else:
        status, info = hacheck.spool.status(service_name)
        if status:
            print 'UP'
            return 0
        else:
            print 'DOWN\t%s' % info.get('reason', '')
            return 1


if __name__ == '__main__':
    sys.exit(main())
