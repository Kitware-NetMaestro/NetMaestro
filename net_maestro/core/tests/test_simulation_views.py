"""Tests for simulation views.

Tests for the PHOLD simulation view including:
- Form submission and validation
- Run creation with correct initial status
- Task triggering
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from django.contrib.auth.models import User
from django.urls import reverse
import pytest

from net_maestro.core.constants import RunStatus
from net_maestro.core.models import Run

if TYPE_CHECKING:
    from django.test import Client


@pytest.mark.django_db
class TestSimulationView:
    """Test the PHOLD simulation view."""

    @pytest.fixture
    def authenticated_client(self, client: Client) -> Client:
        """Create an authenticated client."""
        User.objects.create_user(username="testuser", password="testpass")
        client.login(username="testuser", password="testpass")
        return client

    def test_get_simulation_form(self, authenticated_client: Client) -> None:
        """Test GET request returns simulation form."""
        response = authenticated_client.get(reverse("simulation-config"))

        assert response.status_code == 200
        assert "form" in response.context
        assert "net_maestro/index.html" in [t.name for t in response.templates]

    def test_get_simulation_form_htmx(self, authenticated_client: Client) -> None:
        """Test HTMX GET request returns partial template."""
        response = authenticated_client.get(
            reverse("simulation-config"),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert "net_maestro/partials/simulation.html" in [t.name for t in response.templates]

    @mock.patch("net_maestro.core.views.run_phold_simulation")
    def test_submit_simulation_form(
        self, mock_task: mock.Mock, authenticated_client: Client
    ) -> None:
        """Test successful form submission creates run with PENDING status."""
        form_data = {
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

        response = authenticated_client.post(reverse("simulation-config"), data=form_data)

        # Check redirect
        assert response.status_code == 302
        assert response.url == reverse("analysis-partial")  # type: ignore[attr-defined]

        # Verify run was created with PENDING status
        run = Run.objects.get(name="Test Simulation")
        assert run.status == RunStatus.PENDING

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

    def test_submit_invalid_form(self, authenticated_client: Client) -> None:
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

        response = authenticated_client.post(reverse("simulation-config"), data=form_data)

        # Should not redirect
        assert response.status_code == 200

        # Should have form errors
        assert response.context["form"].errors

        # No run should be created
        assert Run.objects.count() == 0

    def test_unauthenticated_access(self, client: Client) -> None:
        """Test unauthenticated access returns the form (public page)."""
        response = client.get(reverse("simulation-config"))

        # simulation-config is publicly accessible
        assert response.status_code == 200
        assert "form" in response.context
