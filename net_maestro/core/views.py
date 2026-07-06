"""Django views for the NetMaestro core application.

Provides page views for configuration and analysis.
Data loading is driven by selecting a Run on the analysis page.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import HttpResponse
from django.shortcuts import redirect, render

if TYPE_CHECKING:
    from django.http import HttpRequest

from .constants import RunStatus
from .forms import PHOLDSimulationForm
from .models import PHOLDSimulationConfig, Run
from .tasks import run_phold_simulation


def _avail_component_models_context() -> dict[str, object]:
    """Return available models context for the configuration page."""
    return {
        "models": [
            {
                "name": "nw-lp",
                "type": "host",
                "description": """Network LP for compute-node endpoints.
                                Carries an inline workload: block — traffic pattern, message count,
                                timing, payload size.""",
                "parameters": ["traffic", "num_messages", "arrival_time", "payload_size"],
                "icon_class": "ri-organization-chart",
                "usage_count": 3,
            },
            {
                "name": "simplep2p",
                "type": "router",
                "description": "Simple point-to-point router.",
                "parameters": ["routing", "latency", "bandwidth", "chunk_size", "vc_size"],
                "icon_class": "ri-server-line",
                "usage_count": 2,
            },
        ],
    }


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
                "name": "nw-lp",
                "type": "Host",
                "engine": "PDES (CODES)",
                "icon_class": "ri-server-line",
            },
            {
                "name": "simplep2p",
                "type": "Router",
                "engine": "PDES (CODES)",
                "icon_class": "ri-router-fill",
            },
        ],
        "custom_components": [
            {
                "id": 1,
                "name": "High Traffic Host",
                "type": "Host",
                "base_model": "nw-lp",
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
                "base_model": "simplep2p",
                "icon_class": "ri-router-fill",
                "color_class": "text-secondary",
                "badge_class": "badge-secondary",
                "detail_fields": [
                    {"label": "Ingress Bandwidth", "value": "400 Gbps"},
                    {"label": "Egress Bandwidth", "value": "400 Gbps"},
                    {"label": "Ingress Latency", "value": "1.25 ms"},
                    {"label": "Egress Latency", "value": "1.25 ms"},
                    {"label": "Engine", "value": "PDES (CODES)"},
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


def _phold_form_initial_from_config(config: PHOLDSimulationConfig) -> dict[str, object]:
    return {
        "run_identifier": config.run.name,
        "synch": config.synch,
        "avl_size": config.avl_size,
        "nlp": config.nlp,
        "remote": config.remote,
        "mean": config.mean,
        "mult": config.mult,
        "lookahead": config.lookahead,
        "start_events": config.start_events,
        "memory": config.memory,
        "stagger": int(config.stagger),
    }


def _phold_form_data_from_config(config: PHOLDSimulationConfig) -> dict[str, str]:
    initial = _phold_form_initial_from_config(config)
    return {key: str(value) for key, value in initial.items()}


def _phold_form_from_config(config: PHOLDSimulationConfig) -> PHOLDSimulationForm:
    return PHOLDSimulationForm(_phold_form_data_from_config(config))


def _run_phold_from_form(run: Run, form: PHOLDSimulationForm) -> None:
    run_phold_simulation.delay(
        run_id=run.id,
        synch=int(form.cleaned_data["synch"]),
        avl_size=form.cleaned_data["avl_size"],
        nlp=form.cleaned_data["nlp"],
        remote=form.cleaned_data["remote"],
        mean=form.cleaned_data["mean"],
        mult=form.cleaned_data["mult"],
        lookahead=form.cleaned_data["lookahead"],
        start_events=form.cleaned_data["start_events"],
        memory=form.cleaned_data["memory"],
        stagger=bool(int(form.cleaned_data["stagger"])),
    )


def simulation_config(request: HttpRequest) -> HttpResponse:
    """Render the simulation configuration form and handle submission.

    GET: Display the form with PHOLD parameters.
    POST: Create a Run and its configuration. Only triggers a task when "Save and Run"
        was used; "Save" persists the configuration without running it.
    """
    if request.method == "POST":
        form = PHOLDSimulationForm(request.POST)
        if form.is_valid():
            should_run = request.POST.get("action") == "save_and_run"

            # Create Run with PENDING status
            run = Run.objects.create(
                name=form.cleaned_data["run_identifier"],
                status=RunStatus.PENDING,
            )

            # Persist the submitted simulation configuration for this run
            PHOLDSimulationConfig.objects.create(
                run=run,
                synch=int(form.cleaned_data["synch"]),
                avl_size=form.cleaned_data["avl_size"],
                nlp=form.cleaned_data["nlp"],
                remote=form.cleaned_data["remote"],
                mean=form.cleaned_data["mean"],
                mult=form.cleaned_data["mult"],
                lookahead=form.cleaned_data["lookahead"],
                start_events=form.cleaned_data["start_events"],
                memory=form.cleaned_data["memory"],
                stagger=bool(int(form.cleaned_data["stagger"])),
            )

            if should_run:
                # Trigger Celery task to run PHOLD simulation
                run_phold_simulation.delay(
                    run_id=run.id,
                    synch=int(form.cleaned_data["synch"]),
                    avl_size=form.cleaned_data["avl_size"],
                    nlp=form.cleaned_data["nlp"],
                    remote=form.cleaned_data["remote"],
                    mean=form.cleaned_data["mean"],
                    mult=form.cleaned_data["mult"],
                    lookahead=form.cleaned_data["lookahead"],
                    start_events=form.cleaned_data["start_events"],
                    memory=form.cleaned_data["memory"],
                    stagger=bool(int(form.cleaned_data["stagger"])),
                )
                # Redirect to the analysis page so the user can watch the run
                return redirect("analysis-partial")

            # Redirect to the saved simulations list
            return redirect("simulation-config")
    else:
        form = PHOLDSimulationForm()

    context: dict[str, object] = {"form": form}
    partial_template = "net_maestro/partials/new_simulation.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": "simulation", "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)


def edit_simulation_config(request: HttpRequest, run_id: int) -> HttpResponse:
    config = get_object_or_404(PHOLDSimulationConfig.objects.select_related("run"), run_id=run_id)

    if request.method == "POST":
        form = PHOLDSimulationForm(request.POST)
        if form.is_valid():
            should_run = request.POST.get("action") == "save_and_run"
            run_status = RunStatus.PENDING if should_run else RunStatus.SAVED
            run = Run.objects.create(
                name=form.cleaned_data["run_identifier"],
                status=run_status,
            )

            PHOLDSimulationConfig.objects.create(
                run=run,
                synch=int(form.cleaned_data["synch"]),
                avl_size=form.cleaned_data["avl_size"],
                nlp=form.cleaned_data["nlp"],
                remote=form.cleaned_data["remote"],
                mean=form.cleaned_data["mean"],
                mult=form.cleaned_data["mult"],
                lookahead=form.cleaned_data["lookahead"],
                start_events=form.cleaned_data["start_events"],
                memory=form.cleaned_data["memory"],
                stagger=bool(int(form.cleaned_data["stagger"])),
            )

            if should_run:
                _run_phold_from_form(run, form)
                return redirect("analysis-partial")

            return redirect("simulation-config")
    else:
        form = PHOLDSimulationForm(initial=_phold_form_initial_from_config(config))

    context: dict[str, object] = {
        "form": form,
        "form_action": request.path,
        "page_heading": "Edit Simulation",
        "breadcrumb_label": "Edit Simulation",
    }
    partial_template = "net_maestro/partials/new_simulation.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": "simulation", "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)


@require_POST
def run_saved_simulation(request: HttpRequest, run_id: int) -> HttpResponse:
    run = get_object_or_404(Run.objects.select_related("phold_config"), pk=run_id)
    config = run.phold_config

    form = _phold_form_from_config(config)
    if not form.is_valid():
        return redirect("simulation-config")
    run.status = RunStatus.PENDING
    run.save(update_fields=["status"])
    _run_phold_from_form(run, form)
    return redirect("analysis-partial")


def saved_simulations(request: HttpRequest) -> HttpResponse:
    """Render the list of saved PHOLD simulation configurations.

    GET: Display all saved simulation configurations, most recently created first.
    """
    configs = PHOLDSimulationConfig.objects.select_related("run").order_by("-run__created")
    context: dict[str, object] = {"configs": configs}
    partial_template = "net_maestro/partials/saved_simulations.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": "simulation", "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)


def models_list(request: HttpRequest) -> HttpResponse:
    """Render the custom component list.

    TODO: Replace models_context() with database queries.
    TODO: Build absolute action URLs for create, edit, duplicate, and delete once those
    routes are implemented.
    """
    context = _avail_component_models_context()
    partial_template = "net_maestro/partials/models_list.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": "modelsList", "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)


def _new_model_form_context() -> dict[str, object]:
    """Return read-only demo context for the new custom component form.

    TODO: Replace this static host example with a real Django form bound to model-backed
    base component choices and custom component defaults.
    TODO: Keep field metadata in the view so the template can render form sections without
    knowing which fields belong to hosts, routers, or switches.
    """
    return {
        "form_sections": [
            {
                "title": "Model",
                "fields": [
                    {"label": "Name", "value": "New Model"},
                    {"label": "Component Type", "value": "Router"},
                    {"label": "Engine", "value": "PDES (CODES)"},
                    {"label": "Description", "value": "Simple point-to-point router."},
                    {
                        "label": "Parameters",
                        "value": "routing, latency, bandwidth, chunk_size, vc_size",
                    },
                ],
            },
        ],
    }


def model_create(request: HttpRequest) -> HttpResponse:
    """Render the demonstration form for creating a new model component.

    TODO: Render and process a real form for creating a new model.
    TODO: Validate component fields by type, especially host-only traffic fields.
    TODO: Return either a full-page redirect or an HTMX partial update after successful create.
    """
    context = _new_model_form_context()
    partial_template = "net_maestro/partials/model_form.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": "modelsList", "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)


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
