"""Django views for the NetMaestro core application.

Provides the main application view that handles:
- Rendering the main UI template
- Managing data file selection via session state
- Providing CSRF tokens for AJAX requests

Note: The home view supports both GET (display) and POST (file selection) requests.
Currently, the UI uses AJAX POST requests to /api/v1/data/select instead of
traditional form submissions (POST) to this view. This allows file selection without
page reloads.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def event_data(request: HttpRequest) -> HttpResponse:
    """Return event data as JSON."""
    # TODO: Implement event data retrieval
    return HttpResponse("Event data")


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
