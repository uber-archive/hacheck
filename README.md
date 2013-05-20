**hacheck** is a healthcheck-proxying service. It listens on port 3333 and has the following API:

    GET /<protocol>/<service_name>/<port>/<query>

This will check the following locations for service state:

 * `/var/spool/hacheck/all`
 * `/var/spool/hacheck/<service_name>`
 * Depending on the value of `<protocol>`:
  * if `<http>`: `http://localhost:<port>/<query>`
  * if `<tcp>`: Will attempt to connect to port `<port>` on localhost. `<query>` is currently ignored

When it does query the actual service check endpoint, **hacheck** MAY cache the value of that query
for up to 15 seconds.

**hacheck** also comes with the command-line utilities `haup`, `hadown`, and `hastatus`. These take a service name
and manipulate the spool files, allowing you to pre-emptively mark a service as "up" or "down".
