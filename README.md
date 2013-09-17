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

When it does query the actual service check endpoint, **hacheck** MAY cache the value of that query for up to 15 seconds.

**hacheck** also comes with the command-line utilities `haup`, `hadown`, and `hastatus`. These take a service name and manipulate the spool files, allowing you to pre-emptively mark a service as "up" or "down".

### Dependencies

**hacheck** is written in Python and makes extensive use of the [tornado](http://www.tornadoweb.org/en/stable/) asynchronous web framework (specifically, it uses the coroutine stuff in Tornado 3). Unit tests use nose and mock.

It runs on Python 2.6 and above, as well as Python 3.2 and above.

### Use cases

Imagine you want to take down the server `web01` for maintenance. Just SSH to it, then (as root) run `hadown all` and wait however long your HAproxy healthchecking interval is. Do your maintenance, then run `haup all` to put it back in service. So easy!

### License

This work is licensed under the [MIT License](http://opensource.org/licenses/MIT), the contents of which can be found at [LICENSE.txt](LICENSE.txt).
