"""Tests for simulation tasks and management command.

Tests for the PHOLD simulation workflow including:
- Celery chain-based ingestion
- Error handling and status transitions
- Management command behavior
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from django.core.management import call_command
import pytest

from net_maestro.core.constants import RunStatus
from net_maestro.core.tasks.simulation import (
    mark_run_completed,
    mark_run_failed,
    run_phold_simulation,
)
from net_maestro.core.tests.factories import RunFactory

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.django_db
class TestStatusTransitions:
    """Test run status transitions during simulation workflow."""

    def test_mark_run_completed(self) -> None:
        """Test mark_run_completed updates status to COMPLETED."""
        run = RunFactory.create(status=RunStatus.RUNNING)

        mark_run_completed(run.id)

        run.refresh_from_db()
        assert run.status == RunStatus.COMPLETED

    def test_mark_run_completed_missing_run(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test mark_run_completed handles missing run gracefully."""
        mark_run_completed(999999)

        assert "Run 999999 not found when trying to mark as completed" in caplog.text

    def test_mark_run_failed(self) -> None:
        """Test mark_run_failed updates status to FAILED."""
        run = RunFactory.create(status=RunStatus.RUNNING)

        # Mock the request object that Celery passes to error callbacks
        mock_request = mock.Mock(id="test-task-id")
        exc = Exception("Test error")

        mark_run_failed(mock_request, exc, None, run_id=run.id)

        run.refresh_from_db()
        assert run.status == RunStatus.FAILED

    def test_mark_run_failed_missing_run(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test mark_run_failed handles missing run gracefully."""
        mock_request = mock.Mock(id="test-task-id")
        exc = Exception("Test error")

        mark_run_failed(mock_request, exc, None, run_id=999999)

        assert "Run 999999 not found when trying to mark as failed" in caplog.text


@pytest.mark.django_db
class TestRunPHOLDSimulation:
    """Test the run_phold_simulation Celery task."""

    def test_run_phold_simulation_missing_binary_path(self) -> None:
        """Test simulation fails when PHOLD_BINARY_PATH is not configured."""
        # In test settings, PHOLD_BINARY_PATH defaults to empty string via getattr
        run = RunFactory.create(status=RunStatus.PENDING)

        run_phold_simulation(
            run_id=run.id,
            synch=1,
            avl_size=1024,
            nlp=16,
            remote=0.1,
            mean=1.0,
            mult=1.0,
            lookahead=0.1,
            start_events=10,
            memory=256,
            stagger=False,
        )

        run.refresh_from_db()
        assert run.status == RunStatus.FAILED

    @mock.patch("net_maestro.core.tasks.simulation.call_command")
    def test_run_phold_simulation_success(self, mock_call_command: mock.Mock, settings) -> None:
        """Test successful PHOLD simulation execution."""
        settings.PHOLD_BINARY_PATH = "/path/to/phold"
        run = RunFactory.create(status=RunStatus.PENDING)

        run_phold_simulation(
            run_id=run.id,
            synch=1,
            avl_size=1024,
            nlp=16,
            remote=0.1,
            mean=1.0,
            mult=1.0,
            lookahead=0.1,
            start_events=10,
            memory=256,
            stagger=True,
        )

        # Verify run status is set to RUNNING
        run.refresh_from_db()
        assert run.status == RunStatus.RUNNING

        # Verify call_command was called with the command name and positional args
        mock_call_command.assert_called_once()
        call_args = mock_call_command.call_args
        assert call_args[0][0] == "run_phold"

    @mock.patch("net_maestro.core.tasks.simulation.call_command")
    def test_run_phold_simulation_failure(self, mock_call_command: mock.Mock, settings) -> None:
        """Test PHOLD simulation failure updates status correctly."""
        settings.PHOLD_BINARY_PATH = "/path/to/phold"
        mock_call_command.side_effect = Exception("Command failed")

        run = RunFactory.create(status=RunStatus.PENDING)

        run_phold_simulation(
            run_id=run.id,
            synch=1,
            avl_size=1024,
            nlp=16,
            remote=0.1,
            mean=1.0,
            mult=1.0,
            lookahead=0.1,
            start_events=10,
            memory=256,
            stagger=False,
        )

        run.refresh_from_db()
        assert run.status == RunStatus.FAILED


@pytest.mark.django_db
class TestManagementCommandChains:
    """Test the run_phold management command chain behavior."""

    @mock.patch("net_maestro.core.management.commands.run_phold.chain")
    @mock.patch("net_maestro.core.management.commands.run_phold.run_model_task")
    @mock.patch("net_maestro.core.management.commands.run_phold.run_event_task")
    @mock.patch("net_maestro.core.management.commands.run_phold._execute_phold")
    def test_chain_creation_with_files(
        self,
        mock_exec_phold: mock.Mock,
        mock_event_task: mock.Mock,
        mock_model_task: mock.Mock,
        mock_chain: mock.Mock,
        tmp_path: Path,
    ) -> None:
        """Test that ingestion chain is created correctly with files."""
        # Setup mock simulation output
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create fake phold binary (required by click.Path validation)
        fake_phold = tmp_path / "fake_phold"
        fake_phold.write_text("fake binary")

        # Create mock output files with default stats_prefix='phold'
        (output_dir / "phold-evtrace.bin").write_text("event data")
        (output_dir / "phold-model.bin").write_text("model data")

        mock_exec_phold.return_value = None

        # Create a run
        run = RunFactory.create(status=RunStatus.PENDING)

        # Mock task signatures
        mock_event_sig = mock.Mock()
        mock_model_sig = mock.Mock()
        mock_event_task.si.return_value = mock_event_sig
        mock_model_task.si.return_value = mock_model_sig

        # Mock chain
        mock_workflow = mock.Mock()
        mock_chain.return_value = mock_workflow

        # Execute command with required arguments (use positional args for djclick)
        call_command(
            "run_phold",
            "--name",
            "Test Run",
            "--synch",
            "1",
            "--run-id",
            str(run.id),
            "--phold-path",
            str(fake_phold),
            "--output-dir",
            str(output_dir),
        )

        # Verify chain was called with correct tasks
        mock_chain.assert_called_once()
        chain_args = mock_chain.call_args[0]

        # Should have event, model, and mark_completed tasks
        assert len(chain_args) == 3
        assert chain_args[0] == mock_event_sig
        assert chain_args[1] == mock_model_sig
        # Last task should be mark_run_completed

        # Verify error callbacks were attached
        for task in chain_args[:-1]:  # All but the last
            task.link_error.assert_called_once()

        # Verify chain was executed
        mock_workflow.apply_async.assert_called_once()

    @mock.patch("net_maestro.core.management.commands.run_phold.mark_run_completed")
    @mock.patch("net_maestro.core.management.commands.run_phold._execute_phold")
    def test_no_files_still_marks_completed(
        self,
        mock_exec_phold: mock.Mock,
        mock_mark_completed: mock.Mock,
        tmp_path: Path,
    ) -> None:
        """Test that run is marked completed even with no files to ingest."""
        # Setup empty output directory
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        mock_exec_phold.return_value = None

        # Create fake phold binary (required by click.Path validation)
        fake_phold = tmp_path / "fake_phold"
        fake_phold.write_text("fake binary")

        # Create a run
        run = RunFactory.create(status=RunStatus.PENDING)

        # Execute command with required arguments (use positional args for djclick)
        call_command(
            "run_phold",
            "--name",
            "Test Run",
            "--synch",
            "1",
            "--run-id",
            str(run.id),
            "--phold-path",
            str(fake_phold),
            "--output-dir",
            str(output_dir),
        )

        # Verify mark_run_completed was called directly
        mock_mark_completed.delay.assert_called_once_with(run.id)
