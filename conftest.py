import pytest


@pytest.fixture(scope='session')
def celery_config():
    return {'task_always_eager': True}


@pytest.fixture
def web_client():
    from django.test import Client
    return Client()
