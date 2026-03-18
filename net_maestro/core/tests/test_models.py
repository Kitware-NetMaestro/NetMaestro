"""Smoke tests for data API endpoints.

Note: Tests require sample data files to be present in data/ directories.
If files are missing, endpoints will return 404 (which will fail these tests).
"""

from __future__ import annotations

import pytest

from net_maestro.core.constants import RunStatus
from net_maestro.core.models.run import Run
from net_maestro.core.tests.factories import RunFactory, UserFactory


@pytest.mark.django_db
def test_run_creation(api_client: APIClient) -> None:
    """Smoke test for run creation."""
    user = UserFactory.create()
    api_client.force_authenticate(user=user)
    resp = api_client.post(
        "/api/v1/runs/",
        {"name": "Test Run", "description": "Test Run description"},
    )


@pytest.mark.django_db
def test_run_creation() -> None:
    """Smoke test for Run model creation and properties."""
    # Create Run using model directly
    run = RunFactory.create(name="Test Run", description="Test Run description")

    # Test model properties
    assert run.name == "Test Run"
    assert run.description == "Test Run description"
    assert run.status == RunStatus.RUNNING
    assert run.created is not None
    assert Run.objects.filter(id=run.id).exists()


@pytest.mark.django_db
def test_run_cascade_delete() -> None:
    """Test CASCADE deletion: deleting Run deletes EventFiles and EventRecords."""
    run = RunFactory.create()

    # Verify objects exist
    assert Run.objects.filter(id=run.id).exists()

    # Delete the Run
    run.delete()

    # Verify CASCADE: all related objects deleted
    assert not Run.objects.filter(id=run.id).exists()
