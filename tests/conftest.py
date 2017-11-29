import pytest


@pytest.fixture
def web_client():
    from django.test import Client
    return Client()
