"""Smoke tests for data API endpoints.

Note: Tests require sample data files to be present in data/ directories.
If files are missing, endpoints will return 404 (which will fail these tests).
"""

from __future__ import annotations

from django.db import models
import pytest

from net_maestro.core.constants import RunStatus
from net_maestro.core.models.event_file import EventFile
from net_maestro.core.models.event_record import EventRecord
from net_maestro.core.models.model_file import ModelFile
from net_maestro.core.models.model_record import ModelRecord
from net_maestro.core.models.run import Run
from net_maestro.core.models.simulation_file import SimulationFile
from net_maestro.core.models.simulation_pe_record import SimulationPeRecord
from net_maestro.core.tests.factories import (
    EventFileFactory,
    EventRecordFactory,
    ModelFileFactory,
    ModelRecordFactory,
    RunFactory,
    SimulationFileFactory,
    SimulationPeRecordFactory,
)

INTEGER_VALUE = 5
FLOAT_VALUE = 1.5


def _get_model_fields_by_type(model_class, field_type, value):
    """Get field names from a model filtered by field type."""
    return {
        field.name: value
        for field in model_class._meta.fields
        if isinstance(field, field_type) and field.name != "id"
    }


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
    simulation_file = SimulationFileFactory.create(run=run)
    simulation_pe_record1 = SimulationPeRecordFactory.create(simulation_file=simulation_file)
    simulation_pe_record2 = SimulationPeRecordFactory.create(simulation_file=simulation_file)
    model_file = ModelFileFactory.create(run=run)
    model_record1 = ModelRecordFactory.create(model_file=model_file)
    model_record2 = ModelRecordFactory.create(model_file=model_file)

    # Verify objects exist
    assert Run.objects.filter(id=run.id).exists()
    assert EventFile.objects.filter(id=event_file.id).exists()
    assert EventRecord.objects.filter(id=record1.id).exists()
    assert EventRecord.objects.filter(id=record2.id).exists()
    assert SimulationFile.objects.filter(id=simulation_file.id).exists()
    assert SimulationPeRecord.objects.filter(id=simulation_pe_record1.id).exists()
    assert SimulationPeRecord.objects.filter(id=simulation_pe_record2.id).exists()
    assert ModelFile.objects.filter(id=model_file.id).exists()
    assert ModelRecord.objects.filter(id=model_record1.id).exists()
    assert ModelRecord.objects.filter(id=model_record2.id).exists()

    # Delete the Run
    run.delete()

    # Verify CASCADE: all related objects deleted
    assert not Run.objects.filter(id=run.id).exists()
    assert not EventFile.objects.filter(id=event_file.id).exists()
    assert not EventRecord.objects.filter(id=record1.id).exists()
    assert not EventRecord.objects.filter(id=record2.id).exists()
    assert not SimulationFile.objects.filter(id=simulation_file.id).exists()
    assert not SimulationPeRecord.objects.filter(id=simulation_pe_record1.id).exists()
    assert not SimulationPeRecord.objects.filter(id=simulation_pe_record2.id).exists()
    assert not ModelFile.objects.filter(id=model_file.id).exists()
    assert not ModelRecord.objects.filter(id=model_record1.id).exists()
    assert not ModelRecord.objects.filter(id=model_record2.id).exists()


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
    assert event_file in run.event_files.all()


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
    assert event_record in event_file.event_records.all()


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


@pytest.mark.django_db
def test_simulationfile_creation() -> None:
    """Smoke test for SimulationFile model creation and relationships."""
    # Create a Run first
    run = RunFactory.create()

    # Create SimulationFile using factory (handles S3FileField properly)
    sim_file = SimulationFileFactory.create(run=run)

    # Test model properties and relationships
    assert sim_file.run.id == run.id
    assert sim_file.uploaded is not None
    assert sim_file.file is not None  # File field exists
    assert SimulationFile.objects.filter(id=sim_file.id).exists()

    # Test reverse relationship
    assert sim_file in run.simulation_files.all()


@pytest.mark.django_db
def test_simulation_pe_record_creation() -> None:
    """Smoke test for SimulationPeRecord model creation and relationships."""
    # Create dependencies using factories
    sim_file = SimulationFileFactory.create()

    # Use module-level constants for field lists
    int_fields = _get_model_fields_by_type(SimulationPeRecord, models.IntegerField, INTEGER_VALUE)
    float_fields = _get_model_fields_by_type(SimulationPeRecord, models.FloatField, FLOAT_VALUE)

    # Create SimulationPeRecord with specific values
    pe_record = SimulationPeRecordFactory.create(
        simulation_file=sim_file, **int_fields, **float_fields
    )

    # Test model properties and relationships
    assert list(int_fields.values()) == [INTEGER_VALUE] * len(int_fields)
    assert list(float_fields.values()) == [FLOAT_VALUE] * len(float_fields)
    assert SimulationPeRecord.objects.filter(id=pe_record.id).exists()

    # Test that pe_record was created with correct simulation_file
    assert pe_record.simulation_file == sim_file

    # Test reverse relationship using the custom related_name="pe_records"
    assert pe_record in sim_file.pe_records.all()


@pytest.mark.django_db
def test_simulation_cascade_delete() -> None:
    """Test CASCADE deletion: deleting SimulationFile deletes SimulationPeRecords."""
    sim_file = SimulationFileFactory.create()
    record1 = SimulationPeRecordFactory.create(simulation_file=sim_file)
    record2 = SimulationPeRecordFactory.create(simulation_file=sim_file)

    # Verify objects exist
    assert SimulationFile.objects.filter(id=sim_file.id).exists()
    assert SimulationPeRecord.objects.filter(id=record1.id).exists()
    assert SimulationPeRecord.objects.filter(id=record2.id).exists()

    # Delete the SimulationFile
    sim_file.delete()

    # Verify CASCADE: all related records deleted
    assert not SimulationFile.objects.filter(id=sim_file.id).exists()
    assert not SimulationPeRecord.objects.filter(id=record1.id).exists()
    assert not SimulationPeRecord.objects.filter(id=record2.id).exists()


@pytest.mark.django_db
def test_model_file_creation() -> None:
    """Smoke test for ModelFile model creation and relationships."""
    # Create dependencies using factories
    run = RunFactory.create()

    # Create ModelFile with specific values
    model_file = ModelFileFactory.create(run=run)

    # Test model properties and relationships
    assert ModelFile.objects.filter(id=model_file.id).exists()

    # Test reverse relationship
    assert model_file in run.model_files.all()


@pytest.mark.django_db
def test_model_record_creation() -> None:
    """Smoke test for ModelRecord model creation and relationships."""
    # Create dependencies using factories
    model_file = ModelFileFactory.create()

    # Use module-level constants for field lists
    int_fields = _get_model_fields_by_type(ModelRecord, models.IntegerField, INTEGER_VALUE)
    float_fields = _get_model_fields_by_type(ModelRecord, models.FloatField, FLOAT_VALUE)

    # Create ModelRecord with specific values
    model_record = ModelRecordFactory.create(model_file=model_file, **int_fields, **float_fields)

    # Test model properties and relationships
    assert list(int_fields.values()) == [INTEGER_VALUE] * len(int_fields)
    assert list(float_fields.values()) == [FLOAT_VALUE] * len(float_fields)
    assert ModelRecord.objects.filter(id=model_record.id).exists()

    # Test that model_record was created with correct model_file
    assert model_record.model_file == model_file

    # Test reverse relationship using the custom related_name="model_records"
    assert model_record in model_file.model_records.all()


@pytest.mark.django_db
def test_model_cascade_delete() -> None:
    """Test CASCADE deletion: deleting ModelFile deletes ModelRecords."""
    model_file = ModelFileFactory.create()
    record1 = ModelRecordFactory.create(model_file=model_file)
    record2 = ModelRecordFactory.create(model_file=model_file)

    # Verify objects exist
    assert ModelFile.objects.filter(id=model_file.id).exists()
    assert ModelRecord.objects.filter(id=record1.id).exists()
    assert ModelRecord.objects.filter(id=record2.id).exists()

    # Delete the ModelFile
    model_file.delete()

    # Verify CASCADE: all related records deleted
    assert not ModelFile.objects.filter(id=model_file.id).exists()
    assert not ModelRecord.objects.filter(id=record1.id).exists()
    assert not ModelRecord.objects.filter(id=record2.id).exists()
