# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('README.md', 'r', encoding="utf-8") as fp:
    long_description = fp.read()

setup_kwargs = {
    'name': 'beancount_cc_importers',
    'version': '0.1.4',
    'description': 'Beancount plugins to import bank debts',
    'long_description': long_description,
    'license': 'GPL-3.0',
    'author': 'Chao Chen',
    'author_email': 'Chao Chen <wenbushi@gmail.com>',
    'maintainer': None,
    'maintainer_email': None,
    'url': 'https://github.com/chen-chao/beancount_cc_importers',
    'packages': find_packages(),
    'package_data': {'': ['*']},
    'long_description_content_type': 'text/markdown',
    'install_requires': [
        'beancount>=2.3.5',
    ],
    'python_requires': '>=3.7',

}

setup(**setup_kwargs)