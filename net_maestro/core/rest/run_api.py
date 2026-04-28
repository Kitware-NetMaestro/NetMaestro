"""REST API endpoints for serving parsed data by Run ID.

Queries database records (EventRecord, ModelRecord, SimulationPeRecord)
that were ingested via the data_ingest management command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

if TYPE_CHECKING:
    from django.db.models import Model
    from rest_framework.request import Request

from net_maestro.core.models import (
    EventRecord,
    ModelRecord,
    Run,
    SimulationPeRecord,
)


def _fields_for_model(
    model: type[Model],
    *,
    exclude: tuple[str, ...] = ("id",),
) -> list[str]:
    """Return field names for a model, excluding specified fields and FKs."""
    return [
        f.name
        for f in model._meta.get_fields()
        if hasattr(f, "column")
        and f.name not in exclude
        and not f.many_to_many
        and not f.related_model
    ]


def _queryset_to_response(
    queryset: Any,
    columns: list[str],
) -> dict[str, Any]:
    """Convert a queryset to the standard {columns, data} response format."""
    records = list(queryset.values(*columns))
    return {
        "columns": columns,
        "data": records,
    }


class RunRossDataView(APIView):
    """Return simulation PE records for a given run."""

    def get(self, _request: Request, run_id: int) -> Response:
        run = get_object_or_404(Run, pk=run_id)
        columns = _fields_for_model(
            SimulationPeRecord,
            exclude=("id", "simulation_file"),
        )
        queryset = SimulationPeRecord.objects.filter(
            simulation_file__result=run.result,
        ).order_by("virtual_time")
        return Response(_queryset_to_response(queryset, columns))


class RunEventDataView(APIView):
    """Return event records for a given run."""

    def get(self, _request: Request, run_id: int) -> Response:
        run = get_object_or_404(Run, pk=run_id)
        columns = _fields_for_model(
            EventRecord,
            exclude=("id", "event_file"),
        )
        queryset = EventRecord.objects.filter(
            event_file__result=run.result,
        )
        return Response(_queryset_to_response(queryset, columns))


class RunModelDataView(APIView):
    """Return model records for a given run."""

    def get(self, _request: Request, run_id: int) -> Response:
        run = get_object_or_404(Run, pk=run_id)
        columns = _fields_for_model(
            ModelRecord,
            exclude=("id", "model_file"),
        )
        queryset = ModelRecord.objects.filter(
            model_file__result=run.result,
        ).order_by("virtual_time")
        return Response(_queryset_to_response(queryset, columns))
