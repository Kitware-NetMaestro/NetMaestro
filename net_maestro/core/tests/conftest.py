from __future__ import annotations

from django.test import Client
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def client() -> Client:
    """Django test client for view tests."""
    return Client()
