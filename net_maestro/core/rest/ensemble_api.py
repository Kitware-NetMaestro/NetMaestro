"""REST endpoints that serve an ensemble's members' time series, for the compare card.

The series are computed and thinned server-side (see `core/series.py`) because the
per-run endpoints return every row, which is too much to pull for several members.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from net_maestro.core.models import Ensemble
from net_maestro.core.series import (
    X_LABEL,
    base_topology,
    entities_for,
    member_series,
    series_metric,
    series_metrics_as_json,
)
from net_maestro.core.sweeps import member_label

if TYPE_CHECKING:
    from rest_framework.request import Request

# More traces than this stop being readable on one chart, and each is a query or two.
MAX_SERIES_MEMBERS = 8


def _bad_request(message: str) -> Response:
    return Response({"error": message}, status=400)


def _member_indexes(raw: str) -> tuple[list[int], str]:
    """Parse `members` into indexes, or return why it can't be parsed."""
    try:
        indexes = [int(part) for part in raw.split(",") if part.strip()]
    except ValueError:
        return [], "members must be a comma-separated list of member indexes"
    if not indexes:
        return [], "members is required"
    if len(indexes) > MAX_SERIES_MEMBERS:
        return [], f"at most {MAX_SERIES_MEMBERS} members"
    return indexes, ""


class EnsembleEntitiesView(APIView):
    """Return the entities a series can be drawn for and the metrics per dataset."""

    def get(self, _request: Request, ensemble_id: int) -> Response:
        ensemble = get_object_or_404(Ensemble, pk=ensemble_id)
        return Response({"entities": entities_for(ensemble), "metrics": series_metrics_as_json()})


class EnsembleSeriesView(APIView):
    """Return one entity's metric over time for up to eight members.

    GET params: `entity` (an id from the entities endpoint), `metric` (a key of that
    entity's dataset), `members` (comma-separated member indexes) and `cumulative`
    (`1`/`0`; deltas default to cumulated, gauges ignore it).
    """

    def get(self, request: Request, ensemble_id: int) -> Response:
        ensemble = get_object_or_404(Ensemble, pk=ensemble_id)
        params = request.query_params

        entity_id = params.get("entity", "")
        entity = next((e for e in entities_for(ensemble) if e["id"] == entity_id), None)
        if entity is None:
            return _bad_request(f"Unknown entity {entity_id!r}")
        metric = series_metric(entity["dataset"], params.get("metric", ""))
        if metric is None:
            return _bad_request(
                f"Unknown metric {params.get('metric', '')!r} for {entity['dataset']}"
            )

        indexes, error = _member_indexes(params.get("members", ""))
        if error:
            return _bad_request(error)
        runs = {
            run.member_index: run
            for run in ensemble.members.filter(member_index__in=indexes).select_related("summary")
        }
        missing = [index for index in indexes if index not in runs]
        if missing:
            return _bad_request(f"No member with index {missing[0]}")

        flag = params.get("cumulative")
        if flag not in (None, "", "0", "1"):
            return _bad_request("cumulative must be 1 or 0")
        cumulative = metric.kind == "delta" and flag != "0"

        base = base_topology(ensemble)
        members: list[dict[str, Any]] = []
        for index in dict.fromkeys(indexes):
            run = runs[index]
            series = member_series(
                run, entity=entity_id, metric=metric.key, cumulative=cumulative, base=base
            )
            members.append(
                {
                    "index": index,
                    "label": member_label(run.member_params or {}),
                    "stats_type": series["stats_type"],
                    "points": series["points"],
                }
            )
        return Response(
            {
                "entity": entity,
                "metric": asdict(metric),
                "cumulative": cumulative,
                "x_label": X_LABEL,
                "members": members,
            }
        )
