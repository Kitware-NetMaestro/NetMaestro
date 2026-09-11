"""Graph-level validation for topologies.

Rules that the db model cannot enforce live here.

Every rule mirrors something the FFW model enforces with `tw_error`.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError

from net_maestro.core.constants import NodeKind

if TYPE_CHECKING:
    from net_maestro.core.models import Topology, TopologyNode

# Keep this number low to avoid overwhelming the user with too many errors.
MAX_REPORTED_PAIRS = 10


def unreachable_pairs(topology: Topology) -> list[tuple[str, str]]:
    """Return ordered (source, target) switch names with no route, sorted by name.

    Mirrors CODES's `compute_routes()`: a BFS per source over outgoing links only,
    where a `-1` next hop means the target was never seen.

    Traffic only originates and terminates at switches that have terminals, so those are the
    pairs that must be connected; but a switch with no terminals is still a valid intermediate
    hop, so every switch is traversable.
    """
    switches: list[TopologyNode] = list(topology.nodes.filter(node_kind=NodeKind.SWITCH))
    names = {switch.id: switch.name for switch in switches}
    adjacency: dict[int, list[int]] = {switch.id: [] for switch in switches}

    for source_id, target_id in topology.links.values_list("source_node_id", "target_node_id"):
        if source_id in adjacency and target_id in adjacency:
            adjacency[source_id].append(target_id)

    endpoints = [switch.id for switch in switches if (switch.terminals or 0) > 0]
    missing: list[tuple[str, str]] = []
    for source_id in endpoints:
        seen = {source_id}
        queue = deque([source_id])
        while queue:
            current_id = queue.popleft()
            for neighbor_id in adjacency[current_id]:
                if neighbor_id not in seen:
                    seen.add(neighbor_id)
                    queue.append(neighbor_id)
        missing.extend(
            (names[source_id], names[target_id]) for target_id in endpoints if target_id not in seen
        )
    return sorted(missing)


def validate_topology(topology: Topology) -> None:
    """Raise ValidationError if `topology` would not load in the FFW model.

    Collects every problem before raising so a caller can show them all at once rather
    than surfacing one per save.
    """
    errors: list[str] = []

    switches = list(topology.nodes.filter(node_kind=NodeKind.SWITCH))
    # "topology YAML defined no switches"
    if not switches:
        errors.append("A topology must define at least one switch.")

    # "topology YAML must define at least two terminals".
    total_terminals = sum(switch.terminals or 0 for switch in switches)
    if total_terminals < 2:
        errors.append(
            f"A topology must define at least two terminals in total, but defines "
            f"{total_terminals}."
        )

    # Re-run the per-row endpoint rules.
    for link in topology.links.select_related("source_node", "target_node"):
        try:
            link.clean()
        except ValidationError as error:
            errors.extend(f"{link}: {message}" for message in error.messages)

    # An unreachable pair is not an error in the model: compute_routes() stores -1 and the
    # run completes, silently dropping the traffic as drop_no_route. Catch it here instead.
    missing = unreachable_pairs(topology)
    if missing:
        shown = ", ".join(
            f"{source} to {target}" for source, target in missing[:MAX_REPORTED_PAIRS]
        )
        if len(missing) > MAX_REPORTED_PAIRS:
            shown += f", and {len(missing) - MAX_REPORTED_PAIRS} more"
        errors.append(
            "Every switch with terminals must be able to route to every other one, "
            "otherwise the model silently drops the traffic between them. "
            f"No route from {shown}."
        )

    if errors:
        raise ValidationError(errors)
