#!/usr/bin/env python
import collections

from setuptools import setup, find_packages
from pip.req import parse_requirements

import hacheck


def get_install_requirements():

    ReqOpts = collections.namedtuple('ReqOpts', ['skip_requirements_regex', 'default_vcs'])

    opts = ReqOpts(None, 'git')

    requires = []
    dependency_links = []

    for ir in parse_requirements('requirements.txt', options=opts):
        if ir is not None:
            if ir.url is not None:
                dependency_links.append(str(ir.url))
            if ir.req is not None:
                requires.append(str(ir.req))
    return requires, dependency_links


install_requires, dependency_links = get_install_requirements()

setup(
    name="hacheck",
    version=hacheck.__version__,
    author="James Brown",
    author_email="jbrown@uber.com",
    url="https://github.com/uber/hacheck",
    license="MIT",
    packages=find_packages(exclude=['tests']),
    keywords=["monitoring", "load-balancing", "networking"],
    description="HAProxy health-check proxying service",
    install_requires=install_requires,
    dependency_links=dependency_links,
    test_suite="nose.collector",
    entry_points={
        'console_scripts': [
            'haup = hacheck.haupdown:up',
            'hadown = hacheck.haupdown:down',
            'hastatus = hacheck.haupdown:status',
            'hacheck = hacheck.main:main',
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
        "Topic :: System :: Monitoring",
    ]
)
