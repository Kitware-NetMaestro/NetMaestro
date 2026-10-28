"""Tests for the sweep registry and grid expansion."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from net_maestro.core.constants import SimulationType, SynchProtocol
from net_maestro.core.sweeps import (
    MAX_ENSEMBLE_MEMBERS,
    SweepError,
    axes_as_json,
    axes_for,
    expand_sweep,
    member_label,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import SettingsWrapper

    from net_maestro.core.topology import Topology

# A and B are joined both ways; B -> C is one-way, and C reaches A one-way, so
# every switch still has an incoming link.
TOPOLOGY_YAML = """
topology:
  switches:
    A:
      terminals: 2
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "64 Gb"
      connections:
        B: "100 Gbps"
    B:
      terminals: 2
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "64 Gb"
      connections:
        A: "100 Gbps"
        C: "50 Gbps"
    C:
      terminals: 2
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "64 Gb"
      connections:
        A: "25 Gbps"
"""

BASE: dict[str, Any] = {"topology_name": "ffw-3-site", "traffic": "random", "np": 1, "sync": 1}


@pytest.fixture
def preset(tmp_path: Path, settings: SettingsWrapper) -> str:
    """Write one topology preset and point the topology directory at it."""
    settings.TOPOLOGY_DIR = tmp_path
    name = BASE["topology_name"]
    (tmp_path / f"{name}.yaml").write_text(TOPOLOGY_YAML, encoding="utf-8")
    (tmp_path / "ffw-other.yaml").write_text(TOPOLOGY_YAML, encoding="utf-8")
    return name


def _expand(spec: list[dict[str, Any]], base: dict[str, Any] | None = None) -> list[Any]:
    return expand_sweep(SimulationType.FFW, base or BASE, spec)


def _bandwidths(topology: Topology) -> dict[tuple[str, str], float]:
    return {(link.source, link.target): link.bandwidth_gbps for link in topology.links}


def test_grid_is_the_product_in_spec_order(preset: str) -> None:
    """The last axis varies fastest, and members are numbered from 1."""
    members = _expand([{"key": "np", "values": [1, 2]}, {"key": "sync", "values": ["1", "2", "3"]}])

    assert [m.index for m in members] == [1, 2, 3, 4, 5, 6]
    assert [m.member_params for m in members] == [
        {"np": 1, "sync": 1},
        {"np": 1, "sync": 2},
        {"np": 1, "sync": 3},
        {"np": 2, "sync": 1},
        {"np": 2, "sync": 2},
        {"np": 2, "sync": 3},
    ]
    assert members[4].params == {**BASE, "np": 2, "sync": 2}
    # Neither axis touches the topology, so no member needs a file of its own.
    assert all(m.topology is None for m in members)


def test_numbers_are_parsed_and_whole_values_kept_whole(preset: str) -> None:
    members = _expand([{"key": "switch_buffer_gb", "values": ["2", 8.0, 2.5]}])

    assert [m.member_params["switch_buffer_gb"] for m in members] == [2, 8, 2.5]
    assert member_label(members[0].member_params) == "switch_buffer_gb=2"


def test_switch_axes_apply_to_every_switch(preset: str) -> None:
    (member,) = _expand(
        [
            {"key": "switch_buffer_gb", "values": [8]},
            {"key": "terminal_bandwidth_gbps", "values": [40]},
        ]
    )

    assert member.topology is not None
    # Still named for its preset: the caller names the derived file.
    assert member.topology.name == preset
    assert {s.switch_buffer_gb for s in member.topology.switches} == {8.0}
    assert {s.terminal_bandwidth_gbps for s in member.topology.switches} == {40.0}


def test_link_axis_sets_both_directions(preset: str) -> None:
    (member,) = _expand(
        [{"key": "link_bandwidth_gbps", "link": {"source": "A", "target": "B"}, "values": [40]}]
    )

    assert member.topology is not None
    assert _bandwidths(member.topology) == {
        ("A", "B"): 40.0,
        ("B", "A"): 40.0,
        ("B", "C"): 50.0,
        ("C", "A"): 25.0,
    }


def test_link_axis_leaves_a_one_way_link_one_way(preset: str) -> None:
    (member,) = _expand(
        [{"key": "link_bandwidth_gbps", "link": {"source": "B", "target": "C"}, "values": [10]}]
    )

    assert member.topology is not None
    bandwidths = _bandwidths(member.topology)
    assert bandwidths[("B", "C")] == 10.0
    assert ("C", "B") not in bandwidths
    assert bandwidths[("A", "B")] == 100.0


def test_an_edit_matching_the_preset_needs_no_topology(preset: str) -> None:
    members = _expand([{"key": "switch_buffer_gb", "values": [64, 8]}])

    assert members[0].topology is None
    assert members[1].topology is not None


def test_topology_axis_applies_before_topology_edits(preset: str) -> None:
    """Edits land on each member's own preset, whatever order the axes were listed in."""
    members = _expand(
        [
            {"key": "switch_buffer_gb", "values": [8]},
            {"key": "topology_name", "values": ["ffw-3-site", "ffw-other"]},
        ]
    )

    assert [m.params["topology_name"] for m in members] == ["ffw-3-site", "ffw-other"]
    assert [m.topology.name for m in members if m.topology] == ["ffw-3-site", "ffw-other"]


def test_member_cap(preset: str) -> None:
    values = list(range(1, MAX_ENSEMBLE_MEMBERS + 2))

    with pytest.raises(SweepError, match=f"{MAX_ENSEMBLE_MEMBERS + 1} members"):
        _expand([{"key": "np", "values": values}])


def test_member_cap_counts_the_product(preset: str) -> None:
    assert len(_expand([{"key": "np", "values": list(range(1, 9))}])) == 8
    with pytest.raises(SweepError, match="65 members"):
        _expand(
            [
                {"key": "np", "values": list(range(1, 14))},
                {"key": "switch_buffer_gb", "values": [1, 2, 3, 4, 5]},
            ]
        )


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ([], "at least one parameter"),
        ([{"key": "rng_seed", "values": [1]}], "rng_seed cannot be swept"),
        (
            [{"key": "np", "values": [1]}, {"key": "np", "values": [2]}],
            "swept more than once",
        ),
        ([{"key": "np", "values": []}], "at least one value"),
        ([{"key": "np"}], "at least one value"),
        ([{"key": "np", "values": ["two"]}], "not a number"),
        ([{"key": "np", "values": [1.5]}], "not a whole number"),
        ([{"key": "np", "values": [0]}], "at least 1"),
        ([{"key": "np", "values": [True]}], "not a number"),
        ([{"key": "np", "values": [2, "2"]}], "listed more than once"),
        ([{"key": "switch_buffer_gb", "values": [-1]}], "at least 0"),
        ([{"key": "link_bandwidth_gbps", "values": [10]}], "choose which link"),
        (
            [{"key": "link_bandwidth_gbps", "link": {"source": "A"}, "values": [10]}],
            "choose which link",
        ),
        (
            [{"key": "link_bandwidth_gbps", "link": {"source": "A", "target": "C"}, "values": [0]}],
            "more than 0",
        ),
        (
            [{"key": "link_bandwidth_gbps", "link": {"source": "A", "target": "C"}, "values": [9]}],
            "A → C is not a link in ffw-3-site",
        ),
        ([{"key": "sync", "values": [99]}], "not one of the available choices"),
        ([{"key": "topology_name", "values": ["nope"]}], "not one of the available choices"),
        (["np"], "must be an object"),
    ],
)
def test_validation_errors(preset: str, spec: list[Any], message: str) -> None:
    with pytest.raises(SweepError, match=message):
        _expand(spec)


def test_unknown_base_topology_is_a_sweep_error(preset: str) -> None:
    with pytest.raises(SweepError, match="Unknown topology"):
        _expand([{"key": "switch_buffer_gb", "values": [8]}], {**BASE, "topology_name": "missing"})


def test_unregistered_simulation_type() -> None:
    assert axes_for(SimulationType.PHOLD) == []
    with pytest.raises(SweepError, match="not available"):
        expand_sweep(SimulationType.PHOLD, {}, [{"key": "np", "values": [1]}])


def test_axes_as_json_shape(preset: str) -> None:
    axes = {axis["key"]: axis for axis in axes_as_json(SimulationType.FFW)}

    assert list(axes) == [
        "topology_name",
        "switch_buffer_gb",
        "terminal_bandwidth_gbps",
        "link_bandwidth_gbps",
        "np",
        "sync",
    ]
    for axis in axes.values():
        assert set(axis) == {
            "key",
            "label",
            "kind",
            "unit",
            "step",
            "integer",
            "minimum",
            "minimum_exclusive",
            "needs_link",
            "choices",
        }
    assert axes["link_bandwidth_gbps"]["needs_link"] is True
    # The editor flags values the server would reject, so it needs the same bounds.
    assert axes["np"]["integer"] is True
    assert axes["np"]["minimum"] == 1
    assert axes["link_bandwidth_gbps"]["minimum_exclusive"] is True
    assert axes["link_bandwidth_gbps"]["unit"] == "Gbps"
    assert axes["np"]["kind"] == "number"
    assert axes["np"]["choices"] == []
    assert axes["sync"]["choices"][0] == {
        "value": str(SynchProtocol.SEQUENTIAL.value),
        "label": "Sequential",
    }
    assert [c["value"] for c in axes["topology_name"]["choices"]] == ["ffw-3-site", "ffw-other"]


def test_topology_choices_hide_generated_topologies(preset: str, tmp_path: Path) -> None:
    (tmp_path / "ffw-3-site-sweep-1-1.yaml").write_text(TOPOLOGY_YAML, encoding="utf-8")

    (axis,) = [a for a in axes_for(SimulationType.FFW) if a.key == "topology_name"]
    assert "ffw-3-site-sweep-1-1" not in {value for value, _ in axis.choices()}


def test_member_label() -> None:
    assert (
        member_label({"switch_buffer_gb": 8, "link_bandwidth_gbps": 40})
        == "switch_buffer_gb=8, link_bandwidth_gbps=40"
    )
