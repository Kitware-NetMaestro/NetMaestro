"""Placeholder API endpoint for querying custom component models.

Returns hard-coded example switch components until the real ComponentModel
table is available from the wan-component-models branch. The response shape
matches what the real endpoint will return so the topology editor can be
wired up against a stable contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.response import Response
from rest_framework.views import APIView

if TYPE_CHECKING:
    from rest_framework.request import Request

PLACEHOLDER_SWITCHES = [
    {
        "id": 1,
        "name": "Core WAN Switch",
        "base_model": "fluid-flow-wan-switch-lp",
        "component_type": "switch",
        "description": "64 Gb buffer, 100 Gbps terminal bandwidth",
        "parameters": {
            "switch_buffer": "64",
            "terminal_bandwidth": "100",
        },
    },
    {
        "id": 2,
        "name": "Edge WAN Switch",
        "base_model": "fluid-flow-wan-switch-lp",
        "component_type": "switch",
        "description": "16 Gb buffer, 100 Gbps terminal bandwidth",
        "parameters": {
            "switch_buffer": "16",
            "terminal_bandwidth": "100",
        },
    },
]


class ComponentModelListView(APIView):
    """List custom component models, optionally filtered by base_model.

    GET /api/v1/component-models/
    GET /api/v1/component-models/?base_model=fluid-flow-wan-switch-lp

    TODO: Replace hard-coded data with ComponentModel.objects queries once
    the wan-component-models branch is merged.
    """

    def get(self, request: Request) -> Response:
        data = PLACEHOLDER_SWITCHES
        base_model = request.query_params.get("base_model")
        if base_model:
            data = [c for c in data if c["base_model"] == base_model]
        return Response(data)
