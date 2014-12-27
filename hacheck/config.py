import yaml


DEFAULTS = {
    'cache_time': (float, 10.0),
    'service_name_header': (str, None),
    'log_path': (str, 'stderr'),
    'mysql_username': (str, None),
    'mysql_password': (str, None),
    'postgresql_username': (str, None),
    'postgresql_password': (str, None),
}


config = {}
for key, (_, default) in DEFAULTS.items():
    config[key] = default


def load_from(path):
    with open(path, 'r') as f:
        c = yaml.load(f)
        for key, value in c.items():
            if key in DEFAULTS:
                constructor, default = DEFAULTS[key]
                config[key] = constructor(value)
    return config
