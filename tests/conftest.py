# coding: utf-8
import os

import django


def pytest_configure():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.test_app.settings')
    django.setup()
