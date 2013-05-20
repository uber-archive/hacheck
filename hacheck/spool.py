import os

config = {
    'spool_root': None,
}


def configure(spool_root):
    if os.path.exists(spool_root):
        if not os.access(spool_root, os.W_OK):
            raise ValueError("No write access to %s" % spool_root)
    else:
        os.mkdir(spool_root, 0750)
    config['spool_root'] = spool_root


def is_up(service_name):
    """Check whether a service is asserted to be up or down.

    :returns: (bool of service status, dict of extra information)
    """
    all_file = os.path.join(config['spool_root'], "all")
    this_file = os.path.join(config['spool_root'], service_name)
    try:
        with open(all_file, 'r') as f:
            return False, {"service": "all", "reason": f.read()}
    except IOError:
        # if we get an exception, "all" is up
        pass

    try:
        with open(this_file, 'r') as f:
            return False, {"service": service_name, "reason": f.read()}
    except IOError:
        # if we get an exception, then so is this service
        return True, {}
