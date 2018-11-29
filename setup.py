#!/usr/bin/env python
import os
import re

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def get_version(package):
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search("__version__ = ['\"]([^'\"]+)['\"]", init_py).group(1)


with open('README.rst') as readme_file:
    readme = readme_file.read()


with open('CHANGELOG.rst') as history_file:
    history = history_file.read()


requirements = [
    'requests>=2.10.0',
    'python-dateutil>=2.5.3',
    'django-model-utils>=3.0.0',
    'celery>=3.1.25',
    'shortuuid>=0.5.0',
]

setup(
    name='django-atol',
    version=get_version('atol'),
    description='Django integration with ATOL online',
    long_description=readme + '\n\n' + history,
    author='MyBook',
    author_email='dev@mybook.ru',
    url='https://github.com/MyBook/django-atol',
    packages=[
        'atol',
        'atol.migrations'
    ],
    package_dir={'atol': 'atol'},
    include_package_data=True,
    install_requires=requirements,
    license='BSD',
    zip_safe=False,
    keywords='atol',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    test_suite='tests',
)
