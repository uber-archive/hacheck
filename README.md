**hacheck** is a healthcheck-proxying service. It listens on port 3333 and has the following API:

    GET /<service_name>/<port>/<query>

This will check the following locations for service state:

 * `/var/spool/hacheck/all`
 * `/var/spool/hacheck/<service_name>`
 * `http://localhost:<port>/<query>`

When it does query the actual service check endpoint, **hacheck** MAY cache the value of that query
for up to 15 seconds.

**hacheck** also comes with the command-line utilities `haup`, `hadown`, and `hastatus`. These take a service name
and manipulate the spool files, allowing you to pre-emptively mark a service as "up" or "down".
