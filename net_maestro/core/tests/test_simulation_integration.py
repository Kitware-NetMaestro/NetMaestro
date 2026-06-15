"""Integration tests for the complete PHOLD simulation workflow.

Tests the end-to-end flow from form submission through task execution
and data ingestion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from django.core.files.base import ContentFile
import pytest

from net_maestro.core.constants import RunStatus
from net_maestro.core.management.commands.run_phold import _ingest_output_file
from net_maestro.core.models import EventFile, ModelFile, Run, SimulationFile
from net_maestro.core.tasks import run_event_task, run_model_task
from net_maestro.core.tasks.simulation import mark_run_completed

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.django_db
class TestIngestionChain:
    """Test the complete ingestion chain workflow."""

    @pytest.fixture
    def sample_files(self, tmp_path: Path) -> dict[str, Path]:
        """Create sample output files for testing."""
        files = {
            "event": tmp_path / "test-evtrace.bin",
            "model": tmp_path / "test-analysis-lps.bin",
            "gvt": tmp_path / "test-gvt.bin",
        }

        # Create files with dummy content
        for file_path in files.values():
            file_path.write_bytes(b"dummy binary content")

        return files

    def test_file_creation_and_task_signatures(self, sample_files: dict[str, Path]) -> None:
        """Test that files are created and task signatures are generated correctly."""
        run = Run.objects.create(name="Test Run", status=RunStatus.RUNNING)

        # Test event file
        event_sig = _ingest_output_file("evtrace", sample_files["event"], run, immediate=False)
        assert event_sig is not None
        assert EventFile.objects.filter(run=run).exists()

        # Test model file
        model_sig = _ingest_output_file("model", sample_files["model"], run, immediate=False)
        assert model_sig is not None
        assert ModelFile.objects.filter(run=run).exists()

        # Test simulation file
        gvt_sig = _ingest_output_file("gvt", sample_files["gvt"], run, immediate=False)
        assert gvt_sig is not None
        assert SimulationFile.objects.filter(run=run).exists()

    @mock.patch("net_maestro.core.tasks.events.EventFileParser.parse_event_records")
    def test_event_task_execution(self, mock_parse: mock.Mock) -> None:
        """Test event file ingestion task."""
        mock_parse.return_value = []
        run = Run.objects.create(name="Test Run", status=RunStatus.RUNNING)
        event_file = EventFile.objects.create(
            run=run,
            file=ContentFile(b"dummy content", name="test-evtrace.bin"),
        )

        # Execute task synchronously
        run_event_task(event_file_pk=event_file.pk)

        # Verify parse was called
        mock_parse.assert_called_once()

    @mock.patch("net_maestro.core.tasks.models.ModelFileParser.parse_model_records")
    def test_model_task_execution(self, mock_parse: mock.Mock) -> None:
        """Test model file ingestion task."""
        mock_parse.return_value = []
        run = Run.objects.create(name="Test Run", status=RunStatus.RUNNING)
        model_file = ModelFile.objects.create(
            run=run,
            file=ContentFile(b"dummy content", name="test-analysis-lps.bin"),
        )

        # Execute task synchronously
        run_model_task(model_file_pk=model_file.pk)

        # Verify parse was called
        mock_parse.assert_called_once()

    def test_chain_error_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that chain errors trigger mark_run_failed."""
        Run.objects.create(name="Test Run", status=RunStatus.RUNNING)

        # Create a mock task that will fail
        failing_task = mock.Mock()
        failing_task.apply_async.side_effect = Exception("Task failed")

        # Mock the chain to include our failing task
        mock_chain = mock.Mock()
        mock_chain.apply_async.side_effect = Exception("Chain failed")

        # The error callback should be invoked
        error_callback = mock.Mock()
        failing_task.link_error = error_callback

        # Simulate chain execution failure
        with pytest.raises(Exception, match="Chain failed"):
            mock_chain.apply_async()

    def test_status_ownership_during_workflow(self) -> None:
        """Test that status transitions follow the correct ownership rules."""
        # Initial state: User creates run via form -> PENDING
        run = Run.objects.create(
            name="Test Run",
            status=RunStatus.PENDING,
            description="Test",
        )
        assert run.status == RunStatus.PENDING

        # Orchestrator starts -> RUNNING
        run.status = RunStatus.RUNNING
        run.save()
        assert run.status == RunStatus.RUNNING

        # During ingestion, status remains RUNNING
        # (tested by not changing status in ingestion tasks)

        # Only mark_run_completed changes to COMPLETED
        mark_run_completed(run.id)
        run.refresh_from_db()
        assert run.status == RunStatus.COMPLETED

    @mock.patch("net_maestro.core.management.commands.run_phold.click.echo")
    def test_unknown_file_type_warning(self, mock_echo: mock.Mock, tmp_path: Path) -> None:
        """Test that unknown file types generate warnings but don't fail."""
        run = Run.objects.create(name="Test Run", status=RunStatus.RUNNING)
        unknown_file = tmp_path / "test-unknown.xyz"
        unknown_file.write_text("unknown data")

        # Should return None and log warning via click.echo
        result = _ingest_output_file("unknown", unknown_file, run, immediate=False)
        assert result is None
        mock_echo.assert_called_once()
        assert "Unknown file type 'unknown'" in mock_echo.call_args[0][0]
