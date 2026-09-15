"""REST API endpoint for serving checked-in topology presets to the canvas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

if TYPE_CHECKING:
    from rest_framework.request import Request

from net_maestro.core.topology import TopologyError, get_topology


class TopologyDetailView(APIView):
    """Return the switches and directed links of one topology preset."""

    def get(self, _request: Request, name: str) -> Response:
        try:
            topology = get_topology(name)
        except TopologyError as exc:
            raise NotFound(str(exc)) from exc
        return Response(topology.as_dict())
