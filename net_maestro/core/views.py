"""Django views for the NetMaestro core application.

Provides page views for configuration and analysis.
Data loading is driven by selecting a Run on the analysis page.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import HttpResponse
from django.shortcuts import render

if TYPE_CHECKING:
    from django.http import HttpRequest

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


def _custom_component_not_implemented(action: str) -> HttpResponse:
    """Return a placeholder response for planned custom component views."""
    return HttpResponse(f"TODO: Implement custom component {action}.", status=501)


def custom_component_list(request: HttpRequest) -> HttpResponse:
    """Render the custom component list placeholder.

    TODO: Replace the hard-coded component cards with a queryset of user/project-scoped
    custom components.
    TODO: Include any base model metadata needed to render type chips, source model chips,
    icons, and detail fields.
    TODO: Add an empty state when the user has not created any custom components.
    TODO: Decide whether this list should support server-side filtering/search before topology
    design needs it.
    """
    return page_view(request, "configuration", "customComponents")


def custom_component_create(_request: HttpRequest) -> HttpResponse:
    """Create a new custom component.

    TODO: Render and process a form for creating a custom component from a base model.
    TODO: Validate component fields by type, especially host-only traffic fields.
    TODO: Persist shared network defaults such as bandwidth and latency.
    TODO: Return either a full-page redirect or an HTMX partial update after successful create.
    """
    return _custom_component_not_implemented("create")


def custom_component_detail(_request: HttpRequest, component_id: int) -> HttpResponse:
    """Show one custom component.

    TODO: Fetch the custom component by ID, scoped to the current user/project.
    TODO: Render a detail view or reusable card partial for HTMX updates.
    TODO: Include related base model metadata and formatted default values.
    """
    return _custom_component_not_implemented(f"detail for component {component_id}")


def custom_component_edit(_request: HttpRequest, component_id: int) -> HttpResponse:
    """Edit an existing custom component.

    TODO: Fetch the custom component by ID, scoped to the current user/project.
    TODO: Render and process a form initialized with the existing component values.
    TODO: Re-run type-specific validation when the base model or component type changes.
    TODO: Refresh the list/card after save without losing the user's place in the UI.
    """
    return _custom_component_not_implemented(f"edit for component {component_id}")


def custom_component_duplicate(_request: HttpRequest, component_id: int) -> HttpResponse:
    """Duplicate an existing custom component.

    TODO: Fetch the source component by ID, scoped to the current user/project.
    TODO: Clone editable fields while assigning a distinct user-facing name.
    TODO: Decide whether duplicate opens the edit form immediately or creates a copy directly.
    TODO: Refresh the custom component list after duplication.
    """
    return _custom_component_not_implemented(f"duplicate for component {component_id}")


def custom_component_delete(_request: HttpRequest, component_id: int) -> HttpResponse:
    """Delete an existing custom component.

    TODO: Fetch the custom component by ID, scoped to the current user/project.
    TODO: Confirm whether the component is used by any topology before deleting.
    TODO: Require confirmation and use POST/DELETE semantics rather than deleting from GET.
    TODO: Refresh the custom component list or return an empty-state partial after deletion.
    """
    return _custom_component_not_implemented(f"delete for component {component_id}")


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
    # TODO: Add custom component context for the configuration page.
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": active_page, "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)
