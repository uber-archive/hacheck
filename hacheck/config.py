import yaml


DEFAULTS = {
    'cache_time': (float, 10.0),
    'service_name_header': (str, None),
    'log_path': (str, 'stderr'),
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
