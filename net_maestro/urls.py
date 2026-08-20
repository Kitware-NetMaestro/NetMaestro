from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions, routers

from net_maestro.core.rest.run_api import (
    RunEventDataView,
    RunModelDataView,
    RunRossDataView,
)

from .core import views

router = routers.SimpleRouter()
# OpenAPI generation
schema_view = get_schema_view(
    openapi.Info(
        title="Net Maestro API",
        default_version="v1",
        description=(
            "**WARNING: Internal API Documentation**\n\n"
            "These APIs are designed for use by the NetMaestro UI only and are "
            "subject to change or removal without notice.\n\n"
            "**Do not build external integrations or scripts against these endpoints.**\n\n"
            "While API versioning (v1, v2, etc.) is used to manage breaking changes, "
            "internal APIs may be deprecated at any time."
        ),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path(
        "", RedirectView.as_view(pattern_name="models-list-partial", permanent=False), name="home"
    ),
    path("accounts/", include("allauth.urls")),
    path("oauth/", include("oauth2_provider.urls")),
    path("admin/", admin.site.urls),
    path("api/v1/s3-upload/", include("s3_file_field.urls")),
    path("api/v1/", include(router.urls)),
    # Run-based data endpoints (serve from DB records)
    path("api/v1/runs/<int:run_id>/ross", RunRossDataView.as_view(), name="api-run-ross"),
    path("api/v1/runs/<int:run_id>/event", RunEventDataView.as_view(), name="api-run-event"),
    path("api/v1/runs/<int:run_id>/model", RunModelDataView.as_view(), name="api-run-model"),
    path("api/docs/redoc/", schema_view.with_ui("redoc"), name="docs-redoc"),
    path("api/docs/swagger/", schema_view.with_ui("swagger"), name="docs-swagger"),
    # Page endpoints
    path(
        "analysis/",
        views.page_view,
        {"partial": "analysis", "active_page": "results"},
        name="analysis-partial",
    ),
    path("analysis/runs/", views.run_list, name="run-list"),
    path(
        "configuration/my-components/",
        views.custom_component_list,
        name="configuration-partial",
    ),
    path(
        "configuration/new-component",
        views.custom_component_create,
        name="custom-component-create",
    ),
    path(
        "configuration/edit/<int:component_id>",
        views.custom_component_edit,
        name="custom-component-edit",
    ),
    path(
        "simulation/config",
        views.saved_simulations,
        name="simulation-config",
    ),
    path(
        "models/",
        views.models_list,
        name="models-list-partial",
    ),
    path(
        "models/new-model",
        views.model_create,
        name="model-create",
    ),
    path(
        "simulation/new-config",
        views.simulation_config,
        name="new-simulation-config",
    ),
    path(
        "simulation/edit-config/<int:run_id>",
        views.edit_simulation_config,
        name="edit-simulation-config",
    ),
    path(
        "simulation/run/<int:run_id>",
        views.run_saved_simulation,
        name="run-saved-simulation",
    ),
]

if settings.DEBUG:
    import debug_toolbar.toolbar

    urlpatterns += [
        *debug_toolbar.toolbar.debug_toolbar_urls(),
        path("__reload__/", include("django_browser_reload.urls")),
    ]
