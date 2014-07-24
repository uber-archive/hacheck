#!/usr/bin/env python

from __future__ import print_function

import contextlib
import json
import optparse
import sys

from six.moves.urllib.request import urlopen

import hacheck.spool


def up():
    return main('up')


def down():
    return main('down')


def halist():
    return main('list')


def status():
    return main('status')


def status_all():
    return main('status_all')


def print_s(fmt_string, *formats):
    """Print function split out for mocking"""
    print(fmt_string % formats)


def main(default_action='status'):
    ACTIONS = ('up', 'down', 'status', 'status_all', 'list')
    parser = optparse.OptionParser(usage='%prog [options] service_name')
    parser.add_option(
        '--spool-root',
        default='/var/spool/hacheck',
        help='Root for spool for service states (default %default)'
    )
    parser.add_option(
        '-a',
        '--action',
        type='choice',
        choices=ACTIONS,
        default=default_action,
        help='Action (one of %s, default %%default)' % ', '.join(ACTIONS, )
    )
    parser.add_option(
        '-r',
        '--reason',
        type=str,
        default="",
        help='Reason string when setting down'
    )
    parser.add_option(
        '-p',
        '--port',
        type=str,
        default=3333,
        help='Port that the hacheck daemon is running on (default %(default)'
    )
    opts, args = parser.parse_args()

    if opts.action in ('status', 'up', 'down'):
        if len(args) != 1:
            parser.error('Wrong number of arguments')
        service_name = args[0]

    hacheck.spool.configure(opts.spool_root, needs_write=True)

    if opts.action == 'list':
        with contextlib.closing(urlopen(
            'http://127.0.0.1:%d/recent' % opts.port,
            timeout=3
        )) as f:
            resp = json.load(f)
            for s in sorted(resp['seen_services']):
                print_s(s)
            return 0
    elif opts.action == 'up':
        hacheck.spool.up(service_name)
        return 0
    elif opts.action == 'down':
        hacheck.spool.down(service_name, opts.reason)
        return 0
    elif opts.action == 'status_all':
        for service_name, info in hacheck.spool.status_all_down():
            print_s('DOWN\t%s\t%s', service_name, info.get('reason', ''))
        return 0
    else:
        status, info = hacheck.spool.status(service_name)
        if status:
            print_s('UP\t%s', service_name)
            return 0
        else:
            print_s('DOWN\t%s\t%s', service_name, info.get('reason', ''))
            return 1


if __name__ == '__main__':
    sys.exit(main())
