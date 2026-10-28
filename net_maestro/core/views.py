"""Django views for the NetMaestro core application.

Provides page views for configuration and analysis.
"""

from __future__ import annotations

from collections import Counter
import csv
import json
import logging
from typing import TYPE_CHECKING, Any, cast

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpRequest

from . import ensemble_stats
from .base_models import BASE_MODEL_BY_NAME, BASE_MODEL_REGISTRY
from .constants import FFWTrafficMode, RunStatus, SimulationType, SynchProtocol
from .forms import ComponentModelForm, EnsembleForm, FFWSimulationForm, PHOLDSimulationForm
from .models import ComponentModel, Ensemble, FFWSimulationConfig, PHOLDSimulationConfig, Run
from .services.ensembles import create_ensemble, launch_ensemble
from .simulation_models import SIMULATION_MODELS
from .summaries import HEADLINE_METRICS, Metric, metrics_for
from .sweeps import MAX_ENSEMBLE_MEMBERS, SweepError, axes_as_json
from .tasks import run_ffw_simulation, run_phold_simulation
from .topology import TopologyError, family_label, get_topology, list_topologies

logger = logging.getLogger(__name__)


def _avail_component_models_context() -> dict[str, object]:
    """Return available models context for the models list page."""
    return {
        "simulation_models": SIMULATION_MODELS,
    }


def _base_models_sidebar_context() -> list[dict[str, object]]:
    """Return base models for the sidebar, derived from the registry."""
    models = [
        {
            "name": m["name"],
            "type": m["component_type"],
            "engine": m["engine"],
            "icon_class": m["icon_class"],
            "disabled": m.get("disabled", False),
        }
        for m in BASE_MODEL_REGISTRY
    ]
    models.sort(key=lambda m: bool(m["disabled"]))
    return models


def _filtered_runs(request: HttpRequest) -> dict[str, object]:
    """Return runs queryset filtered by ?status= and ?q= params."""
    statuses = request.GET.getlist("status")
    search_query = request.GET.get("q", "").strip()
    runs = (
        Run.objects.filter(status__in=statuses)
        if statuses
        else Run.objects.exclude(status=RunStatus.SAVED)
    )
    if search_query:
        runs = runs.filter(name__icontains=search_query)
    return {
        "runs": runs,
        # SAVED runs have no simulation data to analyze; exclude them from filter options.
        "status_choices": [
            (value, label) for value, label in RunStatus.choices if value != RunStatus.SAVED
        ],
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


_COMPONENT_TYPE_STYLE: dict[str, dict[str, str]] = {
    "host": {
        "icon_class": "ri-server-line",
        "color_class": "text-primary",
        "badge_class": "badge-primary",
    },
    "router": {
        "icon_class": "ri-router-fill",
        "color_class": "text-secondary",
        "badge_class": "badge-secondary",
    },
    "switch": {
        "icon_class": "ri-organization-chart",
        "color_class": "text-accent",
        "badge_class": "badge-accent",
    },
}


def _component_to_card(component: ComponentModel) -> dict[str, object]:
    """Convert a ComponentModel instance to the dict shape expected by the template."""
    style = _COMPONENT_TYPE_STYLE.get(component.component_type, {})
    params = component.parameters or {}
    detail_fields = [{"label": k, "value": v} for k, v in params.items()]
    detail_fields.append({"label": "Engine", "value": component.engine})
    return {
        "id": component.pk,
        "name": component.name,
        "type": component.get_component_type_display(),
        "base_model": component.base_model,
        "icon_class": style.get("icon_class", "ri-question-line"),
        "color_class": style.get("color_class", ""),
        "badge_class": style.get("badge_class", "badge-outline"),
        "detail_fields": detail_fields,
    }


def custom_component_list(request: HttpRequest) -> HttpResponse:
    """Render the custom component list from the database."""
    db_components = [_component_to_card(c) for c in ComponentModel.objects.order_by("-created_at")]
    context: dict[str, object] = {
        "base_models": _base_models_sidebar_context(),
        "custom_components": db_components,
    }
    partial_template = "net_maestro/partials/configuration.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": "customComponents", "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)


def _component_form_context(form: ComponentModelForm) -> dict[str, object]:
    """Build the template context shared by create and edit views."""
    params = form.initial.get("parameters") or form.instance.parameters or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except (json.JSONDecodeError, TypeError):
            params = {}
    return {
        "form": form,
        "base_model_registry": BASE_MODEL_REGISTRY,
        "base_model_registry_by_name": BASE_MODEL_BY_NAME,
        "initial_params": params,
    }


def custom_component_create(request: HttpRequest) -> HttpResponse:
    """Create a new custom component backed by ComponentModel."""
    if request.method == "POST":
        form = ComponentModelForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("configuration-partial")
    else:
        initial: dict[str, object] = {}
        base = request.GET.get("base_model", "")
        if base in BASE_MODEL_BY_NAME and not BASE_MODEL_BY_NAME[base].get("disabled"):
            initial["base_model"] = base
        form = ComponentModelForm(initial=initial)

    context = _component_form_context(form)
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
    """Edit an existing custom component."""
    try:
        component = ComponentModel.objects.get(pk=component_id)
    except ComponentModel.DoesNotExist as err:
        raise Http404 from err

    if request.method == "POST":
        form = ComponentModelForm(request.POST, instance=component)
        if form.is_valid():
            form.save()
            return redirect("configuration-partial")
    else:
        form = ComponentModelForm(instance=component)

    context = _component_form_context(form)
    context["is_edit"] = True
    partial_template = "net_maestro/partials/custom_component_form.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": "customComponents", "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)


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
    return {"run_identifier": config.run.name}


def _get_latest_phold_config_or_404(run_id: int) -> PHOLDSimulationConfig:
    """Return the most recently created PHOLDSimulationConfig for a Run.

    TODO: Revisit this "most recent wins" choice once ensembles need to disambiguate
    between multiple configs.
    """
    config = (
        PHOLDSimulationConfig.objects.select_related("run")
        .filter(run_id=run_id)
        .order_by("-id")
        .first()
    )
    if config is None:
        raise Http404(f"No PHOLDSimulationConfig found for run {run_id}")
    return config


def _run_phold(run: Run, config: PHOLDSimulationConfig) -> None:
    run_phold_simulation.delay(
        run_id=run.id,
        synch=config.synch,
        avl_size=config.avl_size,
        nlp=config.nlp,
        remote=config.remote,
        mean=config.mean,
        mult=config.mult,
        lookahead=config.lookahead,
        start_events=config.start_events,
        memory=config.memory,
        stagger=config.stagger,
    )


def _create_run_and_config[Config: PHOLDSimulationConfig | FFWSimulationConfig](
    form: forms.ModelForm[Config], run_status: RunStatus
) -> tuple[Run, Config]:
    """Create a Run and its simulation config atomically from validated form data."""
    with transaction.atomic():
        run = Run.objects.create(
            name=form.cleaned_data["run_identifier"],
            description=form.cleaned_data.get("description", ""),
            status=run_status,
            simulation_type=(
                SimulationType.FFW
                if isinstance(form.instance, FFWSimulationConfig)
                else SimulationType.PHOLD
            ),
        )
        config = form.save(commit=False)
        config.run = run
        config.save()
    return run, config


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

            run_status = RunStatus.PENDING if should_run else RunStatus.SAVED
            run, config = _create_run_and_config(form, run_status)

            if should_run:
                _run_phold(run, config)
                # Redirect to the analysis page so the user can watch the run
                return redirect("analysis-partial")

            # Redirect to the saved simulations list
            return redirect("simulation-config")
    else:
        form = PHOLDSimulationForm()

    context: dict[str, object] = {
        "form": form,
        "form_action": request.path,
        "page_heading": "New Simulation",
        "breadcrumb_label": "New Simulation",
    }
    partial_template = "net_maestro/partials/new_simulation.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": "simulation", "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)


def edit_simulation_config(request: HttpRequest, run_id: int) -> HttpResponse:
    config = _get_latest_phold_config_or_404(run_id)

    if request.method == "POST":
        form = PHOLDSimulationForm(request.POST)
        if form.is_valid():
            should_run = request.POST.get("action") == "save_and_run"
            run_status = RunStatus.PENDING if should_run else RunStatus.SAVED
            # TODO: "Editing" a saved config intentionally clones it into a new Run/config
            # rather than mutating the original. This is a deliberate safeguard against one
            # person's edits overwriting another person's saved work.
            # Revisit once per-user ownership exists and in-place edits are safe to allow.
            #
            # TODO: The cloned run/config currently has no explicit linkage to the source run.
            # Consider associating them so users can trace edit history or re-clone without
            # guesswork.
            run, new_config = _create_run_and_config(form, run_status)

            if should_run:
                _run_phold(run, new_config)
                return redirect("analysis-partial")

            return redirect("simulation-config")
    else:
        form = PHOLDSimulationForm(instance=config, initial=_phold_form_initial_from_config(config))

    context: dict[str, object] = {
        "form": form,
        "form_action": request.path,
        "page_heading": "Clone Simulation",
        "breadcrumb_label": "Clone Simulation",
    }
    partial_template = "net_maestro/partials/new_simulation.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": "simulation", "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)


@require_POST
def run_saved_simulation(request: HttpRequest, run_id: int) -> HttpResponse:
    config = _get_latest_phold_config_or_404(run_id)
    run = config.run

    try:
        config.full_clean()
    except ValidationError as exc:
        logger.warning(
            "Saved config for run %s failed re-validation and could not be run: %s",
            run_id,
            exc.message_dict,
        )
        # TODO: Consider surfacing errors via a toast notification or an HTMX response instead of
        # a redirect so it's clear to the user what happened and why.
        messages.error(request, f'Unable to run "{run.name}": saved configuration is invalid.')
        return redirect("simulation-config")
    run.status = RunStatus.PENDING
    run.save(update_fields=["status"])
    _run_phold(run, config)
    return redirect("analysis-partial")


def _get_latest_ffw_config_or_404(run_id: int) -> FFWSimulationConfig:
    config = (
        FFWSimulationConfig.objects.select_related("run")
        .filter(run_id=run_id)
        .order_by("-id")
        .first()
    )
    if config is None:
        raise Http404(f"No FFWSimulationConfig found for run {run_id}")
    return config


def _run_ffw(run: Run, config: FFWSimulationConfig) -> None:
    run_ffw_simulation.delay(
        run_id=run.id,
        topology_name=config.topology_name,
        traffic=config.traffic,
        np=config.np,
        sync=config.sync,
    )


def _ffw_simulation_form_page(
    request: HttpRequest, *, source: FFWSimulationConfig | None, page_heading: str
) -> HttpResponse:
    """Handle the FFW form for both new and cloned configs.

    A clone is saved as a new Run and config, as PHOLD's edit does.

    A new config takes its topology from a `topology` query parameter when one
    is given, which is how the topology page hands off the preset on screen. A
    name that is not a current preset simply leaves the dropdown unselected;
    the form rejects it on submit like any other invalid choice.
    """
    if request.method == "POST":
        form = FFWSimulationForm(request.POST)
        if form.is_valid():
            should_run = request.POST.get("action") == "save_and_run"
            run_status = RunStatus.PENDING if should_run else RunStatus.SAVED
            run, config = _create_run_and_config(form, run_status)
            if should_run:
                _run_ffw(run, config)
                return redirect("analysis-partial")
            return redirect("simulation-config")
    elif source is not None:
        form = FFWSimulationForm(
            instance=source,
            initial={"run_identifier": source.run.name, "description": source.run.description},
        )
    else:
        topology_name = request.GET.get("topology", "").strip()
        form = FFWSimulationForm(initial={"topology_name": topology_name} if topology_name else {})

    context: dict[str, object] = {
        "form": form,
        "form_action": request.path,
        "page_heading": page_heading,
    }
    partial_template = "net_maestro/partials/new_ffw_simulation.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": "simulation", "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)


def ffw_simulation_config(request: HttpRequest) -> HttpResponse:
    return _ffw_simulation_form_page(request, source=None, page_heading="New FFW Simulation")


def edit_ffw_simulation_config(request: HttpRequest, run_id: int) -> HttpResponse:
    source = _get_latest_ffw_config_or_404(run_id)
    return _ffw_simulation_form_page(request, source=source, page_heading="Clone FFW Simulation")


@require_POST
def run_saved_ffw_simulation(request: HttpRequest, run_id: int) -> HttpResponse:
    config = _get_latest_ffw_config_or_404(run_id)
    run = config.run

    try:
        config.full_clean()
    except ValidationError as exc:
        logger.warning(
            "Saved FFW config for run %s failed re-validation and could not be run: %s",
            run_id,
            exc.message_dict,
        )
        messages.error(request, f'Unable to run "{run.name}": saved configuration is invalid.')
        return redirect("simulation-config")
    run.status = RunStatus.PENDING
    run.save(update_fields=["status"])
    _run_ffw(run, config)
    return redirect("analysis-partial")


def saved_simulations(request: HttpRequest) -> HttpResponse:
    """Render the list of saved simulation configurations.

    GET: Display all saved PHOLD and FFW configurations, most recently created first.
    """
    # TODO: This list is unbounded and will likely grow over time. Consider pagination once
    # the number of saved configs makes this a real usability concern.
    configs: list[PHOLDSimulationConfig | FFWSimulationConfig] = [
        # Ensemble members are listed on their ensemble's page instead, so a sweep
        # does not bury standalone configs under one card per member.
        *PHOLDSimulationConfig.objects.select_related("run").filter(run__ensemble__isnull=True),
        *FFWSimulationConfig.objects.select_related("run").filter(run__ensemble__isnull=True),
    ]
    configs.sort(key=lambda config: config.run.created, reverse=True)
    context: dict[str, object] = {"configs": configs}
    partial_template = "net_maestro/partials/saved_simulations.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": "simulation", "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)


# Statuses that mean a member still has work ahead of it; the detail page polls
# its member table only while one of these remains.
_ACTIVE_STATUSES = frozenset({RunStatus.PENDING, RunStatus.RUNNING})


def _render_page(
    request: HttpRequest, partial_template: str, context: dict[str, object], active_page: str
) -> HttpResponse:
    """Render a partial for HTMX, or the full layout around it for direct navigation."""
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": active_page, "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)


def ensemble_list(request: HttpRequest) -> HttpResponse:
    """Render every ensemble, newest first."""
    ensembles = Ensemble.objects.order_by("-created")
    context: dict[str, object] = {"ensembles": ensembles}
    return _render_page(request, "net_maestro/partials/ensembles.html", context, "ensembles")


def ensemble_create(request: HttpRequest) -> HttpResponse:
    """Render the ensemble form and create the ensemble and its members on submit.

    As with a single run, "Save" stores every member without running it and
    "Save and Run" queues them all. The sweep is checked against the registry
    when the members are expanded, so a bad axis or link surfaces here as a
    form error rather than as a half-created ensemble.
    """
    if request.method == "POST":
        form = EnsembleForm(request.POST)
        if form.is_valid():
            should_run = request.POST.get("action") == "save_and_run"
            ensemble: Ensemble | None = None
            try:
                ensemble = create_ensemble(
                    name=form.cleaned_data["name"],
                    description=form.cleaned_data.get("description", ""),
                    simulation_type=SimulationType.FFW,
                    base_params=form.base_params(),
                    sweep_spec=form.cleaned_data["sweep_spec"],
                    run_status=RunStatus.PENDING if should_run else RunStatus.SAVED,
                )
            except (SweepError, TopologyError) as exc:
                form.add_error(None, str(exc))
            if ensemble is not None:
                if should_run:
                    launch_ensemble(ensemble)
                return redirect("ensemble-detail", ensemble_id=ensemble.pk)
    else:
        topology_name = request.GET.get("topology", "").strip()
        form = EnsembleForm(initial={"topology_name": topology_name} if topology_name else {})

    context: dict[str, object] = {
        "form": form,
        "form_action": request.path,
        # The template serialises this once with json_script; the sweep editor reads it.
        "sweep_axes": axes_as_json(SimulationType.FFW),
        "max_members": MAX_ENSEMBLE_MEMBERS,
    }
    return _render_page(request, "net_maestro/partials/new_ensemble.html", context, "ensembles")


def _axis_summaries(ensemble: Ensemble) -> list[dict[str, object]]:
    """Describe each swept axis for the chips and column headers.

    Choice values are shown by their labels (a sync protocol's name, not its
    number); `labels` maps each stored value to that label for the member rows.
    """
    registry = {axis["key"]: axis for axis in axes_as_json(ensemble.simulation_type)}
    summaries: list[dict[str, object]] = []
    for axis in ensemble.sweep_spec:
        meta = registry.get(axis["key"], {})
        labels = {str(choice["value"]): choice["label"] for choice in meta.get("choices") or []}
        summaries.append(
            {
                "key": axis["key"],
                "label": meta.get("label", axis["key"]),
                "unit": meta.get("unit", ""),
                "values": [labels.get(str(value), value) for value in axis.get("values", [])],
                "link": axis.get("link"),
                "labels": labels,
            }
        )
    return summaries


# The element ids that poll the results partials. A request they trigger is a
# refresh, not a choice the user made, so it must not rewrite the address bar
# with the (possibly older) state baked into its URL.
_POLLING_TRIGGERS = frozenset({"ensemble-members", "ensemble-effects"})

_EN_DASH = "\N{EN DASH}"

# The detail value that says where a metric's extreme happened, shown as the
# cell's tooltip: a peak buffer means little without the switch it was on.
_METRIC_DETAILS = {
    "peak_buffer_occupancy_frac": "peak_buffer_switch",
    "bottleneck_peak_utilization": "bottleneck_link",
    "bottleneck_mean_utilization": "bottleneck_link",
}


def _metric_registry(ensemble: Ensemble, members: list[Run]) -> list[Metric]:
    """Return the metrics this ensemble's members can have.

    Engine metrics exist only for runs that collected engine stats, so they are
    offered only when some member has one; otherwise they would be columns of dashes.
    """
    without = metrics_for(ensemble.simulation_type, with_engine=False)
    with_engine = metrics_for(ensemble.simulation_type, with_engine=True)
    plain = {metric.key for metric in without}
    engine_keys = [metric.key for metric in with_engine if metric.key not in plain]
    has_engine = any(
        ensemble_stats.metric_value(run, key) is not None for run in members for key in engine_keys
    )
    return with_engine if has_engine else without


def _requested_extra_metrics(
    request: HttpRequest, known: dict[str, Metric], shown: list[str]
) -> list[str]:
    """Read `?metrics=a,b`, keeping registry keys not already shown, in order.

    Unknown keys are dropped rather than rejected: the parameter lives in a
    URL someone may have kept from before the registry changed.
    """
    keys: list[str] = []
    for raw in request.GET.getlist("metrics"):
        for part in raw.split(","):
            key = part.strip()
            if key in known and key not in shown and key not in keys:
                keys.append(key)
    return keys


def _with_query(request: HttpRequest, **changes: str) -> str:
    """Return the request's query string with some parameters replaced."""
    query = request.GET.copy()
    for key, value in changes.items():
        query[key] = value
    return query.urlencode()


def _health_view(run: Run, health: dict[str, Any] | None) -> dict[str, str] | None:
    """Return the health icon for a member and the text its tooltip shows.

    A failed member has no summary worth checking, so its icon carries the
    first line of why it failed instead.
    """
    if run.status == RunStatus.FAILED:
        reason = (getattr(run, "failure_reason", "") or "").strip()
        return {"icon": "failed", "title": reason.splitlines()[0] if reason else "Failed"}
    if not health:
        return None
    if health.get("ok"):
        return {"icon": "ok", "title": "All checks passed"}
    failed = [
        f"{check.get('label', check.get('key', ''))}: {check.get('detail', '')}".strip(": ")
        for check in health.get("checks", [])
        if not check.get("ok")
    ]
    return {"icon": "warn", "title": "; ".join(failed) or "A check failed"}


def _metric_cell(run: Run, metric: Metric, row: dict[str, Any], *, delta: bool) -> dict[str, str]:
    """Format one member's value (or its delta) and the tooltip that explains it.

    In delta mode the baseline row keeps its own values, so the reference the
    other rows are measured against stays on screen.
    """
    value = row["values"][metric.key]
    if delta and not row["is_baseline"]:
        display = ensemble_stats.format_metric(
            metric, row["delta_vs_baseline"][metric.key], signed=True
        )
    else:
        display = ensemble_stats.format_metric(metric, value)
    title = ""
    detail_key = _METRIC_DETAILS.get(metric.key)
    if detail_key and row["details"].get(detail_key):
        title = str(row["details"][detail_key])
    elif metric.key == "dropped_mbit":
        delivered = ensemble_stats.metric_value(run, "delivered_frac")
        if delivered is not None:
            title = f"Delivered {delivered * 100:.1f}%"
    return {"display": display, "title": title}


def _stat_tiles(
    ensemble: Ensemble, members: list[Run], headline_metrics: list[Metric]
) -> dict[str, object]:
    """Return the numbers for the tiles above the member table."""
    counts = Counter(run.status for run in members)
    times = [t for run in members if (t := ensemble_stats.wall_time(run)) is not None]
    eta = ensemble_stats.eta_seconds(ensemble, members=members)
    metric_tiles = []
    for metric in headline_metrics:
        tile: dict[str, object] = {"metric": metric, "value": "—", "desc": "No results yet"}
        result = ensemble_stats.spread(ensemble, metric.key, members=members)
        suffix = ensemble_stats.unit_suffix(metric)
        if result is not None:
            low = ensemble_stats.format_number(metric, result["min"])
            high = ensemble_stats.format_number(metric, result["max"])
            tile["desc"] = f"range {low} {_EN_DASH} {high}{suffix}"
            best = result["best"]
            if best is not None:
                value = ensemble_stats.format_metric(metric, best["value"])
                tile["value"] = f"#{best['run'].member_index}: {value}"
                tile["title"] = "Best member"
            else:
                tile["value"] = f"{low} {_EN_DASH} {high}{suffix}"
        else:
            present = [
                (run, v)
                for run in members
                if (v := ensemble_stats.metric_value(run, metric.key)) is not None
            ]
            if present:
                first, first_value = present[0]
                shown = ensemble_stats.format_metric(metric, first_value)
                tile["value"] = f"#{first.member_index}: {shown}"
                tile["desc"] = "One member so far"
        metric_tiles.append(tile)
    return {
        "total": len(members),
        "completed": counts[RunStatus.COMPLETED],
        "failed": counts[RunStatus.FAILED],
        "pending": counts[RunStatus.PENDING] + counts[RunStatus.RUNNING],
        "running": counts[RunStatus.RUNNING],
        "saved": counts[RunStatus.SAVED],
        "wall_time": ensemble_stats.format_duration(sum(times)) if times else "—",
        "eta": ensemble_stats.format_duration(eta) if eta is not None else "",
        "metrics": metric_tiles,
    }


def _results_context(request: HttpRequest, ensemble: Ensemble) -> dict[str, object]:
    """Return everything the member table, its tiles, and the effect card show.

    The detail page and both partials build the same context from the same
    query parameters (`metric`, `delta`, `metrics`), so a partial refreshed on
    its own renders exactly what the full page would.

    The rows carry each member's values in axis order because a template cannot
    index `member_params` by a key held in a variable.
    """
    axes = _axis_summaries(ensemble)
    members = ensemble_stats.load_members(ensemble)
    registry = _metric_registry(ensemble, members)
    by_key = {metric.key: metric for metric in registry}
    headline_keys = [key for key in HEADLINE_METRICS if key in by_key]
    default_metric = "dropped_mbit" if "dropped_mbit" in by_key else next(iter(headline_keys), "")
    requested = request.GET.get("metric", "")
    headline = requested if requested in by_key else default_metric
    delta = request.GET.get("delta") == "1"
    extra_metrics = _requested_extra_metrics(request, by_key, headline_keys)
    columns = [by_key[key] for key in [*headline_keys, *extra_metrics]]

    baseline = ensemble_stats.baseline_member(ensemble, members=members)
    metric_rows = ensemble_stats.member_metrics(
        ensemble, [metric.key for metric in columns], members=members, baseline=baseline
    )
    rows = []
    for run, metric_row in zip(members, metric_rows, strict=True):
        params = run.member_params or {}
        values = []
        for axis in axes:
            value = params.get(str(axis["key"]))
            labels = cast("dict[str, object]", axis["labels"])
            values.append(labels.get(str(value), value))
        rows.append(
            {
                "run": run,
                "values": values,
                "metrics": [_metric_cell(run, m, metric_row, delta=delta) for m in columns],
                "health": _health_view(run, metric_row["health"]),
                "is_baseline": metric_row["is_baseline"],
            }
        )

    extra_param = ",".join(extra_metrics)
    return {
        "ensemble": ensemble,
        "axes": axes,
        "member_rows": rows,
        "polling": any(run.status in _ACTIVE_STATUSES for run in members),
        "query": request.GET.urlencode(),
        "headline": headline,
        "headline_metric": by_key.get(headline),
        "delta": delta,
        "baseline": baseline,
        "metric_columns": columns,
        # #, health, status, and Analyze, around one column per axis and metric.
        "column_count": len(axes) + len(columns) + 4,
        "extra_metrics": extra_metrics,
        "extra_metrics_param": extra_param,
        "extra_columns": [
            {
                "metric": by_key[key],
                "remove_query": _with_query(
                    request, metrics=",".join(k for k in extra_metrics if k != key)
                ),
            }
            for key in extra_metrics
        ],
        "add_metric_options": [
            {
                "key": metric.key,
                "label": metric.label,
                "value": ",".join([*extra_metrics, metric.key]),
            }
            for metric in registry
            if metric.key not in headline_keys and metric.key not in extra_metrics
        ],
        "metric_registry": [{"key": metric.key, "label": metric.label} for metric in registry],
        "stats": _stat_tiles(ensemble, members, [by_key[key] for key in headline_keys]),
        "effects": _effects_view(ensemble, headline, by_key.get(headline), members),
    }


def _effects_view(
    ensemble: Ensemble, metric_key: str, metric: Metric | None, members: list[Run]
) -> dict[str, Any]:
    """Return `effect_table` with display strings added, since templates cannot format."""
    table = ensemble_stats.effect_table(ensemble, metric_key, members=members)

    def fmt(cells: list[dict[str, Any]]) -> None:
        for cell in cells:
            cell["display"] = ensemble_stats.format_metric(metric, cell["metric"])

    if table["kind"] == "series":
        fmt(table["rows"])
    elif table["kind"] == "pivot":
        for row in table["rows"]:
            fmt(row["cells"])
    elif table["kind"] == "main_effects":
        for effect in table["axes"]:
            fmt(effect["rows"])
    return table


def _replace_url(request: HttpRequest, response: HttpResponse, ensemble: Ensemble) -> HttpResponse:
    """Point the address bar at the detail page with the state just chosen.

    So a browser refresh keeps the delta toggle, the extra columns, and the
    effect metric. Polls are left alone (see `_POLLING_TRIGGERS`).
    """
    if request.headers.get("HX-Request") and request.headers.get("HX-Trigger") not in (
        _POLLING_TRIGGERS
    ):
        url = reverse("ensemble-detail", kwargs={"ensemble_id": ensemble.pk})
        query = request.GET.urlencode()
        response["HX-Replace-Url"] = f"{url}?{query}" if query else url
    return response


def ensemble_detail(request: HttpRequest, ensemble_id: int) -> HttpResponse:
    """Render one ensemble: its base settings, its sweep, its members, and their results."""
    ensemble = get_object_or_404(Ensemble, pk=ensemble_id)
    context = _results_context(request, ensemble)
    base = ensemble.base_params or {}
    topology_name = base.get("topology_name", "")
    try:
        topology_label = get_topology(topology_name).label
    except TopologyError:
        # The preset may have been removed since; the stored name still says what ran.
        topology_label = topology_name
    context["base"] = {
        "topology": topology_label,
        "traffic": FFWTrafficMode(base["traffic"]).label if "traffic" in base else "",
        "np": base.get("np", ""),
        "sync": SynchProtocol(base["sync"]).label if "sync" in base else "",
    }
    return _render_page(request, "net_maestro/partials/ensemble_detail.html", context, "ensembles")


def ensemble_members(request: HttpRequest, ensemble_id: int) -> HttpResponse:
    """Return the member table and its tiles, which the detail page polls while members run.

    The response also carries the header's status badge as an out-of-band swap, so
    the roll-up follows the members without a request of its own.
    """
    ensemble = get_object_or_404(Ensemble, pk=ensemble_id)
    response = render(
        request,
        "net_maestro/partials/ensemble_members.html",
        {**_results_context(request, ensemble), "oob": True},
    )
    return _replace_url(request, response, ensemble)


def ensemble_effects(request: HttpRequest, ensemble_id: int) -> HttpResponse:
    """Return the "Effect of each parameter" card, for a metric change or a poll."""
    ensemble = get_object_or_404(Ensemble, pk=ensemble_id)
    response = render(
        request,
        "net_maestro/partials/ensemble_effects.html",
        _results_context(request, ensemble),
    )
    return _replace_url(request, response, ensemble)


def _plot_value(axis: ensemble_stats.AxisInfo, value: Any) -> float | str | None:
    """Return a swept value as the comparison plot compares it.

    The sweep spec keeps values as posted ("8") while member params hold them
    parsed (8, or a sync protocol as 1), so both sides are put in one form: a
    float on a number axis, text on a choice axis. The browser can then find a
    member's value among the axis's values with a plain equality test.
    """
    if value is None:
        return None
    if axis.kind == "number":
        try:
            return float(str(value).strip())
        except ValueError:
            return None
    return str(value)


def ensemble_members_json(_request: HttpRequest, ensemble_id: int) -> JsonResponse:
    """Return every member's swept values and metrics, for the comparison plot.

    The plot needs raw numbers rather than the table's formatted text, and it
    lives outside the polled member region, so it fetches this itself whenever
    that region refreshes. Metrics are the ones the member table offers (engine
    metrics only once some member has one), and values are stored values:
    fractions stay 0-1 and the plot decides how to show them.
    """
    ensemble = get_object_or_404(Ensemble, pk=ensemble_id)
    members = ensemble_stats.load_members(ensemble)
    axes = ensemble_stats.axis_infos(ensemble)
    metrics = _metric_registry(ensemble, members)
    keys = {metric.key for metric in metrics}

    member_rows = []
    for run in sorted(members, key=lambda run: run.member_index or 0):
        summary = ensemble_stats.summary_of(run)
        health = (summary.health or {}) if summary else {}
        params = run.member_params or {}
        member_rows.append(
            {
                "index": run.member_index,
                "run_id": run.pk,
                "status": run.status,
                "health_ok": bool(health["ok"]) if "ok" in health else None,
                "params": {axis.key: _plot_value(axis, params.get(axis.key)) for axis in axes},
                "metrics": {
                    metric.key: ensemble_stats.metric_value(run, metric.key) for metric in metrics
                },
            }
        )
    return JsonResponse(
        {
            "axes": [
                {
                    "key": axis.key,
                    "label": axis.label,
                    "unit": axis.unit,
                    "kind": axis.kind,
                    "link": axis.link,
                    "values": [_plot_value(axis, value) for value in axis.values],
                    "labels": [axis.label_for(value) for value in axis.values],
                }
                for axis in axes
            ],
            "metrics": [
                {
                    "key": metric.key,
                    "label": metric.label,
                    "unit": metric.unit,
                    "lower_is_better": metric.lower_is_better,
                    "is_fraction": ensemble_stats.is_fraction(metric),
                    "digits": metric.digits,
                }
                for metric in metrics
            ],
            "headline": [key for key in HEADLINE_METRICS if key in keys],
            "members": member_rows,
        }
    )


def _csv_cell(value: object) -> object:
    """Write missing values as empty cells, which spreadsheets read as blanks."""
    return "" if value is None else value


def ensemble_export(_request: HttpRequest, ensemble_id: int) -> HttpResponse:
    """Download one row per member: its parameters, every metric, and how it ran.

    Values are written as stored (fractions as 0-1, not percent) so the file
    feeds straight into analysis without undoing the page's formatting.
    """
    ensemble = get_object_or_404(Ensemble, pk=ensemble_id)
    members = ensemble_stats.load_members(ensemble)
    axes = ensemble_stats.axis_infos(ensemble)
    metrics = metrics_for(ensemble.simulation_type, with_engine=True)
    summaries = {run.pk: ensemble_stats.summary_of(run) for run in members}
    detail_keys = sorted(
        {key for summary in summaries.values() if summary for key in (summary.details or {})}
    )

    filename = slugify(ensemble.name) or f"ensemble-{ensemble.pk}"
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "member_index",
            *(axis.key for axis in axes),
            *(metric.key for metric in metrics),
            *detail_keys,
            "health_ok",
            "status",
            # Timed by the task around the whole run; not the engine's own
            # `wall_time_s` metric, which only runs with engine stats carry.
            "run_wall_time_s",
            "topology_name",
        ]
    )
    for run in members:
        summary = summaries[run.pk]
        params = run.member_params or {}
        details = (summary.details or {}) if summary else {}
        health = (summary.health or {}) if summary else {}
        writer.writerow(
            [
                run.member_index,
                *(_csv_cell(params.get(axis.key)) for axis in axes),
                *(_csv_cell(ensemble_stats.metric_value(run, m.key)) for m in metrics),
                *(_csv_cell(details.get(key)) for key in detail_keys),
                _csv_cell(health.get("ok")) if summary else "",
                run.status,
                _csv_cell(ensemble_stats.wall_time(run)),
                _csv_cell(ensemble_stats.topology_name_of(run)),
            ]
        )
    return response


@require_POST
def run_saved_ensemble(request: HttpRequest, ensemble_id: int) -> HttpResponse:
    """Queue every member of an ensemble.

    `launch_ensemble` re-validates each member's config first and launches
    nothing when one no longer validates, e.g. because its topology was removed.
    """
    ensemble = get_object_or_404(Ensemble, pk=ensemble_id)
    try:
        launch_ensemble(ensemble)
    except ValidationError as exc:
        logger.warning("Ensemble %s could not be run: %s", ensemble_id, exc.messages)
        messages.error(
            request, f'Unable to run "{ensemble.name}": a member configuration is invalid.'
        )
    return redirect("ensemble-detail", ensemble_id=ensemble.pk)


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


def topology_page(request: HttpRequest) -> HttpResponse:
    """Render the topology page with the presets available to preview.

    A `family` query parameter narrows the page to one family of topologies,
    which is how the Available Models page opens it on a single model's presets.

    TODO: Replace the read-only preset dropdown with database-backed topologies once
    Topology models exist.
    """
    family = request.GET.get("family", "").strip().lower()
    context: dict[str, object] = {
        "topologies": list_topologies(family or None),
        "family": family,
        "family_label": family_label(family) if family else "",
    }
    partial_template = "net_maestro/partials/topology.html"
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": "topology", "partial_template": partial_template})
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
        # `?run=<id>` opens the page with that run selected, which is how an
        # ensemble's member table links into the plots.
        run_id = request.GET.get("run", "")
        context["preselect_run"] = (
            Run.objects.filter(pk=int(run_id)).first() if run_id.isdigit() else None
        )
    if partial == "configuration":
        db_components = [
            _component_to_card(c) for c in ComponentModel.objects.order_by("-created_at")
        ]
        context.update(
            {
                "base_models": _base_models_sidebar_context(),
                "custom_components": db_components,
            }
        )
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context)
    context.update({"active_page": active_page, "partial_template": partial_template})
    return render(request, "net_maestro/index.html", context)
