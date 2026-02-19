"""Pytest configuration and shared fixtures for core app tests.

Provides reusable test fixtures including authenticated API clients.
Fixtures are automatically discovered by pytest and can be used by any test
function that declares them as parameters.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client(db) -> APIClient:
    """Provide a DRF API client with authentication configured for testing.

    Creates an authenticated API client suitable for testing REST endpoints.
    - In DEBUG mode: Returns unauthenticated client (AllowAny permission)
    - In production mode: Creates and authenticates a test user

    Returns:
        APIClient instance, authenticated if not in DEBUG mode

    Example:
        def test_endpoint(api_client):
            response = api_client.get('/api/v1/data/ross')
            assert response.status_code == 200
    """
    client = APIClient()

    # The data API is public in dev. In tests we keep behavior aligned with production
    # by default, so authenticate.
    if not getattr(settings, 'DEBUG', False):
        user_model = get_user_model()
        # Create test user for authenticated requests
        user = user_model.objects.create_user(username='test-user', password='test-password')
        client.force_authenticate(user=user)

    return client
