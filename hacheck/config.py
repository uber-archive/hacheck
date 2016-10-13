import yaml


def max_or_int(some_str_value):
    if some_str_value == 'max':
        return 'max'
    else:
        return int(some_str_value)


DEFAULTS = {
    'cache_time': (float, 10.0),
    'service_name_header': (str, None),
    'log_path': (str, 'stderr'),
    'mysql_username': (str, None),
    'mysql_password': (str, None),
    'rlimit_nofile': (max_or_int, None),
    'allow_remote_spool_changes': (bool, False),
}


config = {}
for key, (_, default) in DEFAULTS.items():
    config[key] = default


def load_from(path):
    with open(path, 'r') as f:
        c = yaml.safe_load(f)
        for key, value in c.items():
            if key in DEFAULTS:
                constructor, default = DEFAULTS[key]
                config[key] = constructor(value)
    return config
