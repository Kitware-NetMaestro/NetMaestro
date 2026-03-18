"""Smoke tests for data API endpoints.

Note: Tests require sample data files to be present in data/ directories.
If files are missing, endpoints will return 404 (which will fail these tests).
"""

from __future__ import annotations

import pytest

from net_maestro.core.constants import RunStatus
from net_maestro.core.models.event_file import EventFile
from net_maestro.core.models.event_record import EventRecord
from net_maestro.core.models.run import Run
from net_maestro.core.tests.factories import (
    EventFileFactory,
    EventRecordFactory,
    RunFactory,
    UserFactory,
)


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
    """Test CASCADE deletion: deleting Run deletes all related objects."""
    run = RunFactory.create()
    event_file = EventFileFactory.create(run=run)
    record1 = EventRecordFactory.create(event_file=event_file)
    record2 = EventRecordFactory.create(event_file=event_file)

    # Verify objects exist
    assert Run.objects.filter(id=run.id).exists()
    assert EventFile.objects.filter(id=event_file.id).exists()
    assert EventRecord.objects.filter(id=record1.id).exists()
    assert EventRecord.objects.filter(id=record2.id).exists()

    # Delete the Run
    run.delete()

    # Verify CASCADE: all related objects deleted
    assert not Run.objects.filter(id=run.id).exists()
    assert not EventFile.objects.filter(id=event_file.id).exists()
    assert not EventRecord.objects.filter(id=record1.id).exists()
    assert not EventRecord.objects.filter(id=record2.id).exists()


@pytest.mark.django_db
def test_eventfile_creation() -> None:
    """Smoke test for EventFile model creation and relationships."""
    # Create a Run first
    run = RunFactory.create()

    # Create EventFile using factory (handles S3FileField properly)
    event_file = EventFileFactory.create(run=run)

    # Test model properties and relationships
    assert event_file.run.id == run.id
    assert event_file.uploaded is not None
    assert event_file.file is not None  # File field exists
    assert EventFile.objects.filter(id=event_file.id).exists()

    # Test reverse relationship
    assert event_file in run.eventfile_set.all()


@pytest.mark.django_db
def test_event_record_creation() -> None:
    """Smoke test for EventRecord model creation and relationships."""
    # Create dependencies using factories
    event_file = EventFileFactory.create()

    # Create EventRecord with specific values
    event_record = EventRecordFactory.create(
        event_file=event_file,
        source_lp=0.1,
        dest_lp=0.2,
        time_step=0,
        event_type=1.0,
        virtual_send=1.5,
        virtual_receive=2.5,
    )

    # Test model properties and relationships
    assert event_record.event_file.id == event_file.id
    assert event_record.source_lp == 0.1
    assert event_record.dest_lp == 0.2
    assert event_record.time_step == 0
    assert event_record.event_type == 1.0
    assert event_record.virtual_send == 1.5
    assert event_record.virtual_receive == 2.5
    assert EventRecord.objects.filter(id=event_record.id).exists()

    # Test reverse relationship
    assert event_record in event_file.eventrecord_set.all()


@pytest.mark.django_db
def test_eventfile_cascade_delete() -> None:
    """Test CASCADE deletion: deleting EventFile deletes EventRecords."""
    event_file = EventFileFactory.create()
    record1 = EventRecordFactory.create(event_file=event_file)
    record2 = EventRecordFactory.create(event_file=event_file)

    # Verify objects exist
    assert EventFile.objects.filter(id=event_file.id).exists()
    assert EventRecord.objects.filter(id=record1.id).exists()
    assert EventRecord.objects.filter(id=record2.id).exists()

    # Delete the EventFile
    event_file.delete()

    # Verify CASCADE: all related records deleted
    assert not EventFile.objects.filter(id=event_file.id).exists()
    assert not EventRecord.objects.filter(id=record1.id).exists()
    assert not EventRecord.objects.filter(id=record2.id).exists()
