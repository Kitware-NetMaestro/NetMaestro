"""REST API endpoints for reading and saving topology presets."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

if TYPE_CHECKING:
    from typing import Any

    from rest_framework.request import Request

    from net_maestro.core.topology import Topology

from net_maestro.core.topology import (
    DuplicateTopologyError,
    TopologyError,
    from_payload,
    get_topology,
    save_topology,
)


class Conflict(APIException):
    """Raised when saving a topology would take a name that is already in use."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "That topology name is already taken."


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


class TopologyCreateView(APIView):
    """Save a topology as a new preset file."""

    def post(self, request: Request) -> Response:
        try:
            topology = from_payload(request.data)
        except TopologyError as exc:
            raise ValidationError(str(exc)) from exc
        try:
            saved = save_topology(topology)
        except DuplicateTopologyError as exc:
            raise Conflict(str(exc)) from exc
        except TopologyError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(_as_response_data(saved), status=status.HTTP_201_CREATED)
