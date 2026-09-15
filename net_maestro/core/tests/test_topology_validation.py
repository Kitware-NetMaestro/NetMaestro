"""Tests for topology validation."""

from __future__ import annotations

from django.core.exceptions import ValidationError
import pytest

from net_maestro.core.constants import NodeKind
from net_maestro.core.models import Topology, TopologyLink, TopologyNode
from net_maestro.core.tests.factories import (
    GBPS,
    TopologyFactory,
    TopologyLinkFactory,
    TopologyNodeFactory,
)
from net_maestro.core.validation import validate_topology
from net_maestro.core.validation.topology import MAX_REPORTED_PAIRS, unreachable_pairs


def _link(topology: Topology, source: TopologyNode, target: TopologyNode) -> TopologyLink:
    return TopologyLinkFactory.create(topology=topology, source_node=source, target_node=target)


@pytest.fixture
def topology() -> Topology:
    return TopologyFactory.create()


@pytest.mark.django_db
class TestAggregateRules:
    def test_single_switch_topology_is_valid(self, topology: Topology) -> None:
        TopologyNodeFactory.create(topology=topology, name="A")
        validate_topology(topology)

    def test_topology_without_switches_is_invalid(self, topology: Topology) -> None:
        with pytest.raises(ValidationError) as excinfo:
            validate_topology(topology)
        assert "at least one switch" in str(excinfo.value)

    def test_fewer_than_two_terminals_is_invalid(self, topology: Topology) -> None:
        TopologyNodeFactory.create(topology=topology, name="A", terminals=1)
        with pytest.raises(ValidationError) as excinfo:
            validate_topology(topology)
        assert "at least two terminals" in str(excinfo.value)

    def test_terminals_are_summed_across_switches(self, topology: Topology) -> None:
        a = TopologyNodeFactory.create(topology=topology, name="A", terminals=1)
        b = TopologyNodeFactory.create(topology=topology, name="B", terminals=1)
        _link(topology, a, b)
        _link(topology, b, a)
        validate_topology(topology)

    def test_transit_switch_does_not_contribute_terminals(self, topology: Topology) -> None:
        TopologyNodeFactory.create(topology=topology, name="A", terminals=1)
        TopologyNodeFactory.create(topology=topology, name="T", terminals=0)
        with pytest.raises(ValidationError) as excinfo:
            validate_topology(topology)
        assert "at least two terminals" in str(excinfo.value)

    def test_every_problem_is_reported_at_once(self, topology: Topology) -> None:
        other = TopologyFactory.create()
        source = TopologyNodeFactory.create(topology=topology, name="A", terminals=0)
        TopologyLinkFactory.create(
            topology=topology,
            source_node=source,
            target_node=TopologyNodeFactory.create(topology=other, name="X"),
        )
        with pytest.raises(ValidationError) as excinfo:
            validate_topology(topology)
        assert len(excinfo.value.messages) == 2


@pytest.mark.django_db
class TestReachability:
    def test_reference_topology_is_reachable(self, topology: Topology) -> None:
        a = TopologyNodeFactory.create(topology=topology, name="A")
        b = TopologyNodeFactory.create(topology=topology, name="B")
        c = TopologyNodeFactory.create(topology=topology, name="C")
        for source, target in [(a, b), (b, a), (b, c), (c, a), (c, b)]:
            _link(topology, source, target)
        assert unreachable_pairs(topology) == []
        validate_topology(topology)

    def test_disconnected_switches_are_unreachable(self, topology: Topology) -> None:
        TopologyNodeFactory.create(topology=topology, name="A")
        TopologyNodeFactory.create(topology=topology, name="B")
        assert unreachable_pairs(topology) == [("A", "B"), ("B", "A")]
        with pytest.raises(ValidationError) as excinfo:
            validate_topology(topology)
        assert "No route from A to B" in str(excinfo.value)

    def test_links_are_directed(self, topology: Topology) -> None:
        a = TopologyNodeFactory.create(topology=topology, name="A")
        b = TopologyNodeFactory.create(topology=topology, name="B")
        _link(topology, a, b)
        assert unreachable_pairs(topology) == [("B", "A")]

    def test_multi_hop_route_counts_as_reachable(self, topology: Topology) -> None:
        a = TopologyNodeFactory.create(topology=topology, name="A")
        b = TopologyNodeFactory.create(topology=topology, name="B")
        c = TopologyNodeFactory.create(topology=topology, name="C")
        for source, target in [(a, b), (b, c), (c, b), (b, a)]:
            _link(topology, source, target)
        assert unreachable_pairs(topology) == []

    def test_terminal_free_switch_is_traversable_but_not_an_endpoint(
        self, topology: Topology
    ) -> None:
        a = TopologyNodeFactory.create(topology=topology, name="A")
        transit = TopologyNodeFactory.create(topology=topology, name="T", terminals=0)
        b = TopologyNodeFactory.create(topology=topology, name="B")
        for source, target in [(a, transit), (transit, b), (b, transit), (transit, a)]:
            _link(topology, source, target)
        assert unreachable_pairs(topology) == []
        validate_topology(topology)

    def test_dangling_transit_switch_is_ignored(self, topology: Topology) -> None:
        a = TopologyNodeFactory.create(topology=topology, name="A")
        b = TopologyNodeFactory.create(topology=topology, name="B")
        TopologyNodeFactory.create(topology=topology, name="ORPHAN", terminals=0)
        _link(topology, a, b)
        _link(topology, b, a)
        assert unreachable_pairs(topology) == []

    def test_single_terminal_bearing_switch_has_no_pairs(self, topology: Topology) -> None:
        TopologyNodeFactory.create(topology=topology, name="A")
        TopologyNodeFactory.create(topology=topology, name="T", terminals=0)
        assert unreachable_pairs(topology) == []

    def test_self_loop_does_not_make_a_switch_reachable(self, topology: Topology) -> None:
        a = TopologyNodeFactory.create(topology=topology, name="A")
        TopologyNodeFactory.create(topology=topology, name="B")
        _link(topology, a, a)
        assert unreachable_pairs(topology) == [("A", "B"), ("B", "A")]

    def test_cross_topology_link_does_not_create_a_route(self, topology: Topology) -> None:
        other = TopologyFactory.create()
        a = TopologyNodeFactory.create(topology=topology, name="A")
        TopologyNodeFactory.create(topology=topology, name="B")
        TopologyLinkFactory.create(
            topology=topology,
            source_node=a,
            target_node=TopologyNodeFactory.create(topology=other, name="X"),
        )
        assert unreachable_pairs(topology) == [("A", "B"), ("B", "A")]

    def test_long_pair_list_is_truncated(self, topology: Topology) -> None:
        count = MAX_REPORTED_PAIRS + 2
        for index in range(count):
            TopologyNodeFactory.create(topology=topology, name=f"S{index:02d}")
        missing = unreachable_pairs(topology)
        assert len(missing) == count * (count - 1)
        with pytest.raises(ValidationError) as excinfo:
            validate_topology(topology)
        assert f"and {len(missing) - MAX_REPORTED_PAIRS} more" in str(excinfo.value)


@pytest.mark.django_db
class TestLinkEndpointRules:
    def test_link_between_switches_in_one_topology_is_valid(self, topology: Topology) -> None:
        link = TopologyLink(
            topology=topology,
            source_node=TopologyNodeFactory.create(topology=topology, name="A"),
            target_node=TopologyNodeFactory.create(topology=topology, name="B"),
            bandwidth=30 * GBPS,
        )
        link.full_clean()

    def test_endpoint_in_another_topology_is_invalid(self, topology: Topology) -> None:
        other = TopologyFactory.create()
        link = TopologyLink(
            topology=topology,
            source_node=TopologyNodeFactory.create(topology=topology, name="A"),
            target_node=TopologyNodeFactory.create(topology=other, name="X"),
            bandwidth=30 * GBPS,
        )
        with pytest.raises(ValidationError) as excinfo:
            link.full_clean()
        assert "target_node" in excinfo.value.message_dict

    def test_terminal_endpoint_is_invalid(self, topology: Topology) -> None:
        terminal = TopologyNodeFactory.create(
            topology=topology,
            name="A.0",
            node_kind=NodeKind.TERMINAL,
            terminals=None,
            terminal_bandwidth=None,
            switch_buffer=None,
        )
        link = TopologyLink(
            topology=topology,
            source_node=TopologyNodeFactory.create(topology=topology, name="A"),
            target_node=terminal,
            bandwidth=30 * GBPS,
        )
        with pytest.raises(ValidationError) as excinfo:
            link.full_clean()
        assert excinfo.value.message_dict["target_node"] == ["A link endpoint must be a switch."]

    def test_missing_endpoint_is_reported_by_clean_fields(self, topology: Topology) -> None:
        link = TopologyLink(topology=topology, bandwidth=30 * GBPS)
        with pytest.raises(ValidationError) as excinfo:
            link.full_clean()
        assert "source_node" in excinfo.value.message_dict

    def test_programmatic_links_are_caught_at_graph_level(self, topology: Topology) -> None:
        other = TopologyFactory.create()
        a = TopologyNodeFactory.create(topology=topology, name="A")
        b = TopologyNodeFactory.create(topology=topology, name="B")
        _link(topology, a, b)
        _link(topology, b, a)
        TopologyLinkFactory.create(
            topology=topology,
            source_node=a,
            target_node=TopologyNodeFactory.create(topology=other, name="X"),
        )
        with pytest.raises(ValidationError) as excinfo:
            validate_topology(topology)
        assert "same topology" in str(excinfo.value)


@pytest.mark.django_db
class TestModelToleratedCasesStayAllowed:
    def test_self_loop_is_allowed(self, topology: Topology) -> None:
        switch = TopologyNodeFactory.create(topology=topology, name="A")
        link = TopologyLink(
            topology=topology, source_node=switch, target_node=switch, bandwidth=30 * GBPS
        )
        link.full_clean()

    def test_zero_bandwidth_is_allowed(self, topology: Topology) -> None:
        link = TopologyLink(
            topology=topology,
            source_node=TopologyNodeFactory.create(topology=topology, name="A"),
            target_node=TopologyNodeFactory.create(topology=topology, name="B"),
            bandwidth=0,
        )
        link.full_clean()


@pytest.mark.django_db
class TestOrderIndexAllocation:
    def test_indices_are_allocated_per_topology(self) -> None:
        first = TopologyFactory.create()
        second = TopologyFactory.create()
        for _ in range(3):
            TopologyNodeFactory.create(topology=first)
            TopologyNodeFactory.create(topology=second)
        for candidate in (first, second):
            assert list(candidate.nodes.values_list("order_index", flat=True)) == [0, 1, 2]

    def test_first_index_is_zero(self) -> None:
        assert TopologyFactory.create().next_order_index() == 0

    def test_deleting_a_node_leaves_a_gap(self) -> None:
        topology = TopologyFactory.create()
        nodes = [TopologyNodeFactory.create(topology=topology) for _ in range(3)]
        nodes[1].delete()
        assert topology.next_order_index() == 3
        assert list(topology.nodes.values_list("order_index", flat=True)) == [0, 2]
