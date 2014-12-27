[![Build Status](https://travis-ci.org/uber/hacheck.png)](https://travis-ci.org/uber/hacheck)

**hacheck** is a healthcheck-proxying service. It listens on port 3333, speaks HTTP, and has the following API:

    GET /<protocol>/<service_name>/<port>/<query>

This will check the following locations for service state:

 * `/var/spool/hacheck/all`
 * `/var/spool/hacheck/<service_name>`
 * Depending on the value of `<protocol>`:
  * if `http`: `http://localhost:<port>/<query>`
  * if `tcp`: will attempt to connect to port `<port>` on localhost. `<query>` is currently ignored
  * if `spool`: will only check the spool state
  * if `mysql` and the `mysql_username` and `mysql_password` are set, will do a login and quit on the requested mysql port; `<query>` is ignored and no logical database is selected.
  * if `username` and the `username_username` and `username_password` are set, will do a login, SELECT 1, and quit on the requested username port; `<query>` is the logical database name

When it does query the actual service check endpoint, **hacheck** MAY cache the value of that query for some amount of time

**hacheck** also comes with the command-line utilities `haup`, `hadown`, and `hastatus`. These take a service name and manipulate the spool files, allowing you to pre-emptively mark a service as "up" or "down".

### Dependencies

**hacheck** is written in Python and makes extensive use of the [tornado](http://www.tornadoweb.org/en/stable/) asynchronous web framework (specifically, it uses the coroutine stuff in Tornado 3). Unit tests use nose and mock.

It runs on Python 2.6 and above, as well as Python 3.2 and above.

### Use cases

Imagine you want to take down the server `web01` for maintenance. Just SSH to it, then (as root) run `hadown all` and wait however long your HAproxy healthchecking interval is. Do your maintenance, then run `haup all` to put it back in service. So easy!

### Configuration

`hacheck` accepts a `-c` flag which should point to a YAML-formatted configuration file. Some notable properties of this file:
* `cache_time`: The duration for which check results may be cached
* `service_name_header`: If set, the name of a header which will be populated with the service name on HTTP checks
* `log_path`: Either the string `"stdout"`, the string `"stderr"`, or a fully-qualified path to a file to write logs to. Uses a [WatchedFileHandler](http://docs.python.org/2/library/logging.handlers.html#watchedfilehandler) and ought to play nicely with logrotate
* `mysql_username`: username to use when logging into mysql for checks
* `mysql_password`: password to use when logging into mysql for checks
* `postgresql_username`: username to use when logging into postgresql for checks
* `postgresql_password`: password to use when logging into postgresql for checks

### License

This work is licensed under the [MIT License](http://opensource.org/licenses/MIT), the contents of which can be found at [LICENSE.txt](LICENSE.txt).
