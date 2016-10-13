#!/usr/bin/env python
import collections
import sys

from setuptools import setup, find_packages
from pip.req import parse_requirements
from pip.download import PipSession


def get_install_requirements(path):

    ReqOpts = collections.namedtuple('ReqOpts', ['skip_requirements_regex', 'default_vcs', 'isolated_mode'])

    opts = ReqOpts(None, 'git', False)

    requires = []
    dependency_links = []

    session = PipSession()

    for ir in parse_requirements(path, options=opts, session=session):
        if ir is not None:
            if getattr(ir, 'url', getattr(ir, 'link', None)) is not None:
                dependency_links.append(str(getattr(ir, 'url', getattr(ir, 'link'))))
            if ir.req is not None:
                requires.append(str(ir.req))
    return requires, dependency_links


install_requires, dependency_links = get_install_requirements('requirements.txt')
if sys.version_info < (3, 0, 0):
    install_requires += get_install_requirements('requirements-py2.txt')[0]

setup(
    name="hacheck",
    version="0.12.0",
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
            'hashowdowned = hacheck.haupdown:status_downed',
            'hastatus = hacheck.haupdown:status',
            'halist = hacheck.haupdown:halist',
            'hacheck = hacheck.main:main',
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
        "Topic :: System :: Monitoring",
    ]
)
