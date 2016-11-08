"""compatibility classes for py2.6, py3, or anything else strange"""

import contextlib
import collections
import sys


def Counter(*args):
    c = collections.defaultdict(lambda: 0)
    if args:
        c.update(args[0])
    return c


@contextlib.contextmanager
def nested3(*managers):
    """Combine multiple context managers into a single nested context manager.

   This function has been deprecated in favour of the multiple manager form
   of the with statement.

   The one advantage of this function over the multiple manager form of the
   with statement is that argument unpacking allows it to be
   used with a variable number of context managers as follows:

      with nested(*managers):
          do_something()

    """
    exits = []
    vars = []
    exc = (None, None, None)
    try:
        for mgr in managers:
            exit = mgr.__exit__
            enter = mgr.__enter__
            vars.append(enter())
            exits.append(exit)
        yield vars
    except:
        exc = sys.exc_info()
    finally:
        while exits:
            exit = exits.pop()
            try:
                if exit(*exc):
                    exc = (None, None, None)
            except:
                exc = sys.exc_info()
        if exc != (None, None, None):
            # Don't rely on sys.exc_info() still containing
            # the right information. Another exception may
            # have been raised and caught by an exit method
            raise exc[1]


def bchr3(c):
    return bytes((c,))


def bchr2(c):
    return chr(c)


if sys.version_info < (3, 0):
    nested = contextlib.nested
    bchr = bchr2
else:
    nested = nested3
    bchr = bchr3
