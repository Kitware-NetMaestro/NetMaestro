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


def _custom_component_context() -> dict[str, object]:
    """Return custom component context for the configuration page.

    TODO: Replace this hard-coded wireframe data with database-backed queries once custom
    component and base model persistence exists.
    """
    return {
        "base_models": [
            {
                "name": "ESNet Switch",
                "type": "Switch",
                "engine": "PDES (ROSS)",
                "icon_class": "ri-organization-chart",
            },
            {
                "name": "ESNet Host",
                "type": "Host",
                "engine": "PDES (ROSS)",
                "icon_class": "ri-server-line",
            },
            {
                "name": "ESNet Router",
                "type": "Router",
                "engine": "PDES (ROSS)",
                "icon_class": "ri-router-fill",
            },
        ],
        "custom_components": [
            {
                "id": 1,
                "name": "High Traffic Host",
                "type": "Host",
                "base_model": "ESNet Host",
                "icon_class": "ri-server-line",
                "color_class": "text-primary",
                "badge_class": "badge-primary",
                "detail_fields": [
                    {"label": "Ingress Bandwidth", "value": "100 Gbps"},
                    {"label": "Egress Bandwidth", "value": "100 Gbps"},
                    {"label": "Ingress Latency", "value": "0.75 ms"},
                    {"label": "Egress Latency", "value": "0.75 ms"},
                    {"label": "Traffic", "value": "Synthetic Workload"},
                ],
            },
            {
                "id": 2,
                "name": "Regional Backbone Router",
                "type": "Router",
                "base_model": "ESNet Router",
                "icon_class": "ri-router-fill",
                "color_class": "text-secondary",
                "badge_class": "badge-secondary",
                "detail_fields": [
                    {"label": "Ingress Bandwidth", "value": "400 Gbps"},
                    {"label": "Egress Bandwidth", "value": "400 Gbps"},
                    {"label": "Ingress Latency", "value": "1.25 ms"},
                    {"label": "Egress Latency", "value": "1.25 ms"},
                    {"label": "Engine", "value": "PDES (ROSS)"},
                    {"label": "Role", "value": "Backbone Transit"},
                ],
            },
            {
                "id": 3,
                "name": "Edge Aggregation Switch",
                "type": "Switch",
                "base_model": "ESNet Switch",
                "icon_class": "ri-organization-chart",
                "color_class": "text-accent",
                "badge_class": "badge-accent",
                "detail_fields": [
                    {"label": "Ingress Bandwidth", "value": "200 Gbps"},
                    {"label": "Egress Bandwidth", "value": "200 Gbps"},
                    {"label": "Ingress Latency", "value": "0.50 ms"},
                    {"label": "Egress Latency", "value": "0.50 ms"},
                    {"label": "Engine", "value": "PDES (ROSS)"},
                    {"label": "Role", "value": "Edge Aggregation"},
                ],
            },
        ],
    }


def _new_component_form_context() -> dict[str, object]:
    """Return read-only demo context for the new custom component form.

    TODO: Replace this static host example with a real Django form bound to model-backed
    base component choices and custom component defaults.
    TODO: Keep field metadata in the view so the template can render form sections without
    knowing which fields belong to hosts, routers, or switches.
    """
    return {
        "component_type": "Host",
        "base_model": "ESNet Host",
        "engine": "PDES (ROSS)",
        "form_sections": [
            {
                "title": "Component",
                "fields": [
                    {"label": "Name", "value": "New Host Component"},
                    {"label": "Type", "value": "Host"},
                    {"label": "Base Model", "value": "ESNet Host"},
                    {"label": "Engine", "value": "PDES (ROSS)"},
                ],
            },
            {
                "title": "Network Defaults",
                "fields": [
                    {"label": "Ingress Bandwidth", "value": "100 Gbps"},
                    {"label": "Egress Bandwidth", "value": "100 Gbps"},
                    {"label": "Ingress Latency", "value": "0.75 ms"},
                    {"label": "Egress Latency", "value": "0.75 ms"},
                ],
            },
            {
                "title": "Host Traffic Defaults",
                "fields": [
                    {"label": "Traffic", "value": "Synthetic Workload"},
                ],
            },
        ],
    }


def _component_to_form_context(component: dict[str, object]) -> dict[str, object]:
    """Convert a component dict to the form_sections format expected by the form template.

    TODO: Replace this with model-backed lookups when custom components are persisted.
    TODO: Split detail_fields into type-specific sections (Network Defaults vs Host Traffic
    Defaults) based on component type instead of assuming a flat list.
    """
    # Infer engine from base model for demo purposes
    base_model = component.get("base_model", "")
    engine = "PDES (ROSS)" if isinstance(base_model, str) and "ESNet" in base_model else "Unknown"

    return {
        "component_type": component.get("type"),
        "base_model": component.get("base_model"),
        "engine": engine,
        "form_sections": [
            {
                "title": "Component",
                "fields": [
                    {"label": "Name", "value": component.get("name")},
                    {"label": "Type", "value": component.get("type")},
                    {"label": "Base Model", "value": component.get("base_model")},
                    {"label": "Engine", "value": engine},
                ],
            },
            {
                "title": "Network Defaults",
                "fields": component.get("detail_fields", []),
            },
        ],
    }


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
    """Return a temporary 501 response for planned custom component views."""
    return HttpResponse(f"TODO: Implement custom component {action}.", status=501)


def custom_component_list(request: HttpRequest) -> HttpResponse:
    """Render the custom component list.

    TODO: Replace _custom_component_context() with database queries.
    TODO: Build absolute action URLs for create, edit, duplicate, and delete once those
    routes are implemented.
    TODO: Decide whether this list should support server-side filtering/search before topology
    design needs it.
    """
    context = _custom_component_context()
    partial_template = "net_maestro/partials/configuration.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": "customComponents", "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)


def custom_component_create(request: HttpRequest) -> HttpResponse:
    """Render the demonstration form for creating a new custom component.

    TODO: Render and process a real form for creating a custom component from a base model.
    TODO: Load base model choices from the same source used by _custom_component_context().
    TODO: Validate component fields by type, especially host-only traffic fields.
    TODO: Persist shared network defaults such as bandwidth and latency.
    TODO: Return either a full-page redirect or an HTMX partial update after successful create.
    """
    context = _new_component_form_context()
    partial_template = "net_maestro/partials/custom_component_form.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": "customComponents", "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)


def custom_component_detail(_request: HttpRequest, component_id: int) -> HttpResponse:
    """Show one custom component.

    TODO: Fetch the custom component by ID, scoped to the current user/project.
    TODO: Reuse the same context shape as the list view for detail/card partial rendering.
    TODO: Include related base model metadata and formatted default values.
    """
    return _custom_component_not_implemented(f"detail for component {component_id}")


def custom_component_edit(request: HttpRequest, component_id: int) -> HttpResponse:
    """Render the demonstration form for editing an existing custom component.

    TODO: Fetch the custom component by ID, scoped to the current user/project.
    TODO: Render and process a real form initialized with the existing component values.
    TODO: Re-run type-specific validation when the base model or component type changes.
    TODO: Refresh the list or component card after save without losing the user's place in the UI.
    """
    context = _custom_component_context()
    components = context.get("custom_components", [])
    if not isinstance(components, list):
        components = []
    component = next((c for c in components if c.get("id") == component_id), None)
    if not component:
        return HttpResponse(f"Component {component_id} not found.", status=404)
    form_context = _component_to_form_context(component)
    form_context["is_edit"] = True
    partial_template = "net_maestro/partials/custom_component_form.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, form_context)
    form_context.update({"active_page": "customComponents", "partial_template": partial_template})
    return render(request, "net_maestro/index.html", form_context)


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
    if partial == "configuration":
        context.update(_custom_component_context())
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": active_page, "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)
