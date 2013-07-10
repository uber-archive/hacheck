import os

config = {
    'spool_root': None,
}


def configure(spool_root, needs_write=False):
    access_required = os.W_OK | os.R_OK if needs_write else os.R_OK
    if os.path.exists(spool_root):
        if not os.access(spool_root, access_required):
            raise ValueError("Insufficient access to %s" % spool_root)
    else:
        os.mkdir(spool_root, 0o750)
    config['spool_root'] = spool_root


def is_up(service_name):
    """Check whether a service is asserted to be up or down. Includes the logic
    for checking system-wide all state

    :returns: (bool of service status, dict of extra information)
    """
    all_up, all_info = status("all")
    if all_up:
        return status(service_name)
    else:
        return all_up, all_info


def status(service_name):
    """Check whether a service is asserted to be up or down, without checking
    the system-wide 'all' state.

    :returns: (bool of service status, dict of extra information)
    """
    try:
        with open(os.path.join(config['spool_root'], service_name), 'r') as f:
            reason = f.read()
            return False, {'service': service_name, 'reason': reason}
    except IOError:
        return True, {'service': service_name, 'reason': ''}


def status_all_down():
    """List all down services

    :returns: Iterable of pairs of (service name, dict of extra information)
    """
    for service_name in os.listdir(config['spool_root']):
        up, info = status(service_name)
        if not up:
            yield service_name, info


def up(service_name):
    try:
        os.unlink(os.path.join(config['spool_root'], service_name))
    except OSError:
        pass


def down(service_name, reason=""):
    with open(os.path.join(config['spool_root'], service_name), 'w') as f:
        f.write(reason)
