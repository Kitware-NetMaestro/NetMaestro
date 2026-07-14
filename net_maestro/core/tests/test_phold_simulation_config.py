"""Tests for PHOLDSimulationConfig validation.

Verifies field and model level constraints that mirror the PHOLD engine's own requirements.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
import pytest

from net_maestro.core.models import PHOLDSimulationConfig, Run


def _build_config(**overrides: object) -> PHOLDSimulationConfig:
    """Build an in-memory PHOLDSimulationConfig with valid defaults, minus overrides."""
    run = Run.objects.create(name="Test Run")
    defaults: dict[str, object] = {
        "run": run,
        "synch": 3,
        "avl_size": 18,
        "nlp": 8,
        "remote": 0.25,
        "mean": 2.0,
        "mult": 1.4,
        "lookahead": 1.0,
        "start_events": 1,
        "memory": 100,
        "stagger": False,
    }
    defaults.update(overrides)
    return PHOLDSimulationConfig(**defaults)


@pytest.mark.django_db
class TestPHOLDSimulationConfigValidation:
    """Test PHOLDSimulationConfig field and cross-field validation."""

    def test_valid_config_passes_full_clean(self) -> None:
        config = _build_config()
        config.full_clean()

    @pytest.mark.parametrize("lookahead", [0.09, 1.01])
    def test_lookahead_out_of_range_is_invalid(self, lookahead: float) -> None:
        """PHOLD hard-errors if lookahead > 1.0; keep a small positive lower bound too."""
        config = _build_config(lookahead=lookahead, mean=2.0)

        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert "lookahead" in exc_info.value.message_dict

    def test_lookahead_at_upper_bound_is_valid(self) -> None:
        config = _build_config(lookahead=1.0, mean=2.0)
        config.full_clean()

    def test_mean_not_greater_than_lookahead_is_invalid(self) -> None:
        """Test that mean == lookahead is invalid.

        PHOLD computes mean - lookahead as the exponential rate parameter, which must
        stay positive.
        """
        config = _build_config(mean=1.0, lookahead=1.0)

        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert "mean" in exc_info.value.message_dict

    def test_mean_greater_than_lookahead_is_valid(self) -> None:
        config = _build_config(mean=1.5, lookahead=1.0)
        config.full_clean()

    @pytest.mark.parametrize("remote", [-0.1, 1.1])
    def test_remote_out_of_probability_range_is_invalid(self, remote: float) -> None:
        """Remote is used as a probability, so it must stay within [0, 1]."""
        config = _build_config(remote=remote)

        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert "remote" in exc_info.value.message_dict

    @pytest.mark.parametrize("nlp", [0, -1])
    def test_nlp_must_be_positive(self, nlp: int) -> None:
        config = _build_config(nlp=nlp)

        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert "nlp" in exc_info.value.message_dict

    @pytest.mark.parametrize("start_events", [0, -1])
    def test_start_events_must_be_positive(self, start_events: int) -> None:
        config = _build_config(start_events=start_events)

        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert "start_events" in exc_info.value.message_dict

    def test_memory_cannot_be_negative(self) -> None:
        config = _build_config(memory=-1)

        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert "memory" in exc_info.value.message_dict

    def test_mult_below_one_is_invalid(self) -> None:
        config = _build_config(mult=0.5)

        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert "mult" in exc_info.value.message_dict
