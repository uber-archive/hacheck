#!/usr/bin/env python
from setuptools import setup, find_packages

import hacheck


with open('requirements.txt') as f:
    required = f.read().splitlines()


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
    install_requires=required,
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
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
        "Topic :: System :: Monitoring",
    ]
)
