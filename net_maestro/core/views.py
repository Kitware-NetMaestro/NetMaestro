"""Django views for the NetMaestro core application.

Provides page views for configuration and analysis.
Data loading is driven by selecting a Run on the analysis page.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import render

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

from .constants import RunStatus
from .models import Run


def _filtered_runs(request: HttpRequest) -> dict[str, object]:
    """Return runs queryset filtered by ?status= and ?q= params."""
    statuses = request.GET.getlist("status")
    search_query = request.GET.get("q", "").strip()
    runs = Run.objects.all()
    if statuses:
        runs = runs.filter(status__in=statuses)
    if search_query:
        runs = runs.filter(name__icontains=search_query)
    return {
        "runs": runs,
        "status_choices": RunStatus.choices,
        "selected_statuses": statuses,
        "search_query": search_query,
    }


def run_list(request: HttpRequest) -> HttpResponse:
    """Return just the runs list partial (used by HTMX filter)."""
    context = _filtered_runs(request)
    return render(request, "net_maestro/partials/run_list.html", context)


def page_view(
    request: HttpRequest,
    partial: str,
    active_page: str,
) -> HttpResponse:
    """Render a page using its partial template.

    For HTMX requests, returns only the partial fragment.
    For direct navigation, renders the partial inside the base layout.
    """
    partial_template = f"net_maestro/partials/{partial}.html"
    context: dict[str, object] = {}
    if partial == "analysis":
        context.update(_filtered_runs(request))
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": active_page, "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)
