"""REST API endpoint for querying custom component models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.response import Response
from rest_framework.views import APIView

if TYPE_CHECKING:
    from rest_framework.request import Request

from net_maestro.core.models import ComponentModel


class ComponentModelListView(APIView):
    """List custom component models, optionally filtered by base_model.

    GET /api/v1/component-models/
    GET /api/v1/component-models/?base_model=fluid-flow-wan-switch-lp
    """

    def get(self, request: Request) -> Response:
        qs = ComponentModel.objects.order_by("name")
        base_model = request.query_params.get("base_model")
        if base_model:
            qs = qs.filter(base_model=base_model)
        data = [
            {
                "id": c.id,
                "name": c.name,
                "base_model": c.base_model,
                "component_type": c.component_type,
                "description": c.description,
                "parameters": c.parameters or {},
            }
            for c in qs
        ]
        return Response(data)
