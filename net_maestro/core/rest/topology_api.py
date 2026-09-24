"""REST API endpoints for reading topology presets."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

if TYPE_CHECKING:
    from typing import Any

    from rest_framework.request import Request

    from net_maestro.core.topology import Topology

from net_maestro.core.topology import TopologyError, get_topology


def _as_response_data(topology: Topology) -> dict[str, Any]:
    """Return the topology payload plus the URL the canvas loads it from."""
    data = topology.as_dict()
    data["url"] = reverse("api-topology-detail", kwargs={"name": data["name"]})
    return data


class TopologyDetailView(APIView):
    """Return the switches and directed links of one topology preset."""

    def get(self, _request: Request, name: str) -> Response:
        try:
            topology = get_topology(name)
        except TopologyError as exc:
            raise NotFound(str(exc)) from exc
        return Response(_as_response_data(topology))


class TopologySimulationInputsView(APIView):
    """Return what a traffic config has to take from one topology."""

    def get(self, _request: Request, name: str) -> Response:
        try:
            topology = get_topology(name)
        except TopologyError as exc:
            raise NotFound(str(exc)) from exc
        return Response(topology.simulation_inputs())
