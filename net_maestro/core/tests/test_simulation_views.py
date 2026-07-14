"""Tests for simulation views.

Tests for the PHOLD simulation view including:
- Form submission and validation
- Run creation with correct initial status
- Task triggering
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest import mock

from django.urls import reverse
from django.utils import timezone
import pytest

from net_maestro.core.constants import RunStatus
from net_maestro.core.models import PHOLDSimulationConfig, Run

if TYPE_CHECKING:
    from django.test import Client


@pytest.mark.django_db
class TestSimulationView:
    """Test the PHOLD simulation view."""

    def test_get_simulation_form(self, client: Client) -> None:
        """Test GET request returns simulation form."""
        response = client.get(reverse("new-simulation-config"))

        assert response.status_code == 200
        assert "form" in response.context
        assert "net_maestro/index.html" in [t.name for t in response.templates]

    def test_get_simulation_form_htmx(self, client: Client) -> None:
        """Test HTMX GET request returns partial template."""
        response = client.get(
            reverse("new-simulation-config"),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert "net_maestro/partials/new_simulation.html" in [t.name for t in response.templates]

    @mock.patch("net_maestro.core.views.run_phold_simulation")
    def test_submit_simulation_form_save_and_run(
        self, mock_task: mock.Mock, client: Client
    ) -> None:
        """Test "Save and Run" submission creates run/config and triggers the task."""
        form_data = {
            "action": "save_and_run",
            "run_identifier": "Test Simulation",
            "synch": "1",
            "avl_size": "18",
            "nlp": "8",
            "remote": "0.25",
            "mean": "1.0",
            "mult": "1.4",
            "lookahead": "1.0",
            "start_events": "1",
            "memory": "100",
            "stagger": "0",
        }

        response = client.post(reverse("new-simulation-config"), data=form_data)

        # Save & Run redirects to analysis so users can monitor the run immediately.
        assert response.status_code == 302
        assert response.headers["Location"] == reverse("analysis-partial")

        # Verify run was created with PENDING status
        run = Run.objects.get(name="Test Simulation")
        assert run.status == RunStatus.PENDING

        # Verify the configuration was persisted
        config = PHOLDSimulationConfig.objects.get(run=run)
        assert config.synch == 1
        assert config.avl_size == 18

        # Verify task was called with correct arguments
        mock_task.delay.assert_called_once_with(
            run_id=run.id,
            synch=1,
            avl_size=18,
            nlp=8,
            remote=0.25,
            mean=1.0,
            mult=1.4,
            lookahead=1.0,
            start_events=1,
            memory=100,
            stagger=False,
        )

    @mock.patch("net_maestro.core.views.run_phold_simulation")
    def test_submit_simulation_form_save_only(self, mock_task: mock.Mock, client: Client) -> None:
        """Save-only submissions stay on the saved simulations page and skip the task."""
        form_data = {
            "action": "save",
            "run_identifier": "Saved Simulation",
            "synch": "1",
            "avl_size": "18",
            "nlp": "8",
            "remote": "0.25",
            "mean": "1.0",
            "mult": "1.4",
            "lookahead": "1.0",
            "start_events": "1",
            "memory": "100",
            "stagger": "0",
        }

        response = client.post(reverse("new-simulation-config"), data=form_data)

        # Check redirect
        assert response.status_code == 302
        assert response.headers["Location"] == reverse("simulation-config")

        # Verify run and configuration were created with SAVED status
        run = Run.objects.get(name="Saved Simulation")
        assert run.status == RunStatus.SAVED
        assert PHOLDSimulationConfig.objects.filter(run=run).exists()

        # Verify the task was NOT triggered
        mock_task.delay.assert_not_called()

    def test_submit_invalid_form(self, client: Client) -> None:
        """Test invalid form submission returns errors."""
        form_data = {
            "run_identifier": "",  # Required field
            "synch": "1",
            "avl_size": "18",
            "nlp": "8",
            "remote": "0.25",
            "mean": "1.0",
            "mult": "1.4",
            "lookahead": "1.0",
            "start_events": "1",
            "memory": "100",
            "stagger": "0",
        }

        response = client.post(reverse("new-simulation-config"), data=form_data)

        # Should not redirect
        assert response.status_code == 200

        # Should have form errors
        assert response.context["form"].errors

        # No run should be created
        assert Run.objects.count() == 0

    def test_unauthenticated_access(self, client: Client) -> None:
        """Test unauthenticated access returns the form (public page)."""
        response = client.get(reverse("new-simulation-config"))

        # new-simulation-config is publicly accessible
        assert response.status_code == 200
        assert "form" in response.context


@pytest.mark.django_db
class TestSavedSimulationsView:
    """Test the saved simulations list view."""

    def test_list_empty(self, client: Client) -> None:
        """Test the list view renders with no saved configurations."""
        response = client.get(reverse("simulation-config"))

        assert response.status_code == 200
        assert list(response.context["configs"]) == []
        assert "net_maestro/index.html" in [t.name for t in response.templates]

    def test_list_htmx(self, client: Client) -> None:
        """Test HTMX GET request returns the partial template."""
        response = client.get(
            reverse("simulation-config"),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert "net_maestro/partials/saved_simulations.html" in [t.name for t in response.templates]

    def test_list_shows_saved_configs(self, client: Client) -> None:
        """Test saved configurations are listed, most recently created first."""
        older_run = Run.objects.create(name="Older Run", status=RunStatus.PENDING)
        older_run.created = timezone.now() - timedelta(days=1)
        older_run.save(update_fields=["created"])
        PHOLDSimulationConfig.objects.create(run=older_run)
        newer_run = Run.objects.create(name="Newer Run", status=RunStatus.PENDING)
        newer_run.created = timezone.now()
        newer_run.save(update_fields=["created"])
        PHOLDSimulationConfig.objects.create(run=newer_run)

        response = client.get(reverse("simulation-config"))

        assert response.status_code == 200
        configs = list(response.context["configs"])
        assert [config.run_id for config in configs] == [newer_run.id, older_run.id]


@pytest.mark.django_db
class TestEditSimulationView:
    def _create_config(self) -> PHOLDSimulationConfig:
        run = Run.objects.create(name="Original Run", status=RunStatus.SAVED)
        return PHOLDSimulationConfig.objects.create(
            run=run,
            synch=3,
            avl_size=18,
            nlp=8,
            remote=0.25,
            mean=1.0,
            mult=1.4,
            lookahead=1.0,
            start_events=1,
            memory=100,
            stagger=False,
        )

    def test_edit_get_prefills_form(self, client: Client) -> None:
        config = self._create_config()

        response = client.get(reverse("edit-simulation-config", args=[config.run.id]))

        assert response.status_code == 200
        form = response.context["form"]
        assert form["run_identifier"].value() == "Original Run"
        assert form["avl_size"].value() == 18

    @mock.patch("net_maestro.core.views.run_phold_simulation")
    def test_edit_save_updates_config(self, mock_task: mock.Mock, client: Client) -> None:
        config = self._create_config()
        form_data = {
            "action": "save",
            "run_identifier": "Updated Run",
            "synch": "2",
            "avl_size": "20",
            "nlp": "10",
            "remote": "0.5",
            "mean": "2.0",
            "mult": "1.8",
            "lookahead": "1.2",
            "start_events": "3",
            "memory": "200",
            "stagger": "1",
        }

        response = client.post(
            reverse("edit-simulation-config", args=[config.run.id]),
            data=form_data,
        )

        assert response.status_code == 302
        assert response.headers["Location"] == reverse("simulation-config")

        config.refresh_from_db()
        new_run = Run.objects.get(name="Updated Run")
        assert new_run.status == RunStatus.SAVED
        new_config = PHOLDSimulationConfig.objects.get(run=new_run)
        assert new_config.avl_size == 20
        assert new_config.stagger is True
        # Original config remains unchanged
        config.refresh_from_db()
        assert config.run.name == "Original Run"
        assert config.avl_size == 18
        mock_task.delay.assert_not_called()

    def test_edit_clone_shows_both_runs_in_saved_list(self, client: Client) -> None:
        config = self._create_config()
        form_data = {
            "action": "save",
            "run_identifier": "Cloned Run",
            "synch": "2",
            "avl_size": "20",
            "nlp": "9",
            "remote": "0.4",
            "mean": "1.5",
            "mult": "1.7",
            "lookahead": "1.1",
            "start_events": "2",
            "memory": "150",
            "stagger": "0",
        }

        response = client.post(
            reverse("edit-simulation-config", args=[config.run.id]),
            data=form_data,
        )

        assert response.status_code == 302

        list_response = client.get(reverse("simulation-config"))
        assert list_response.status_code == 200
        run_names = [cfg.run.name for cfg in list_response.context["configs"]]
        assert run_names == ["Cloned Run", "Original Run"]

    @mock.patch("net_maestro.core.views.run_phold_simulation")
    def test_edit_save_and_run_triggers_task(self, mock_task: mock.Mock, client: Client) -> None:
        config = self._create_config()
        form_data = {
            "action": "save_and_run",
            "run_identifier": "Run Again",
            "synch": "3",
            "avl_size": "18",
            "nlp": "8",
            "remote": "0.25",
            "mean": "1.0",
            "mult": "1.4",
            "lookahead": "1.0",
            "start_events": "1",
            "memory": "100",
            "stagger": "0",
        }

        response = client.post(
            reverse("edit-simulation-config", args=[config.run.id]),
            data=form_data,
        )

        assert response.status_code == 302
        assert response.headers["Location"] == reverse("analysis-partial")

        new_run = Run.objects.get(name="Run Again")
        assert new_run.status == RunStatus.PENDING
        mock_task.delay.assert_called_once()

    @mock.patch("net_maestro.core.views.run_phold_simulation")
    def test_run_saved_simulation_shortcut(self, mock_task: mock.Mock, client: Client) -> None:
        config = self._create_config()

        response = client.post(reverse("run-saved-simulation", args=[config.run.id]))

        assert response.status_code == 302
        assert response.headers["Location"] == reverse("analysis-partial")

        config.run.refresh_from_db()
        assert config.run.status == RunStatus.PENDING
        mock_task.delay.assert_called_once()

    @mock.patch("net_maestro.core.views.run_phold_simulation")
    def test_run_saved_simulation_invalid_config_shows_error(
        self, mock_task: mock.Mock, client: Client
    ) -> None:
        """An invalid saved config surfaces an error message instead of failing silently."""
        config = self._create_config()
        config.avl_size = 5  # Below the form/model MinValueValidator(10)
        config.save(update_fields=["avl_size"])

        response = client.post(reverse("run-saved-simulation", args=[config.run.id]), follow=True)

        assert response.status_code == 200
        assert response.redirect_chain[-1] == (reverse("simulation-config"), 302)
        messages = [str(m) for m in response.context["messages"]]
        assert any("Unable to run" in message for message in messages)

        config.run.refresh_from_db()
        assert config.run.status == RunStatus.SAVED
        mock_task.delay.assert_not_called()
