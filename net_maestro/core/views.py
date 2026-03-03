"""Django views for the NetMaestro core application.

Provides the main application view that handles:
- Rendering the main UI template
- Managing data file selection via session state
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from net_maestro.core.models.run import Run


def home(request: HttpRequest) -> HttpResponse:
    """Render the main application page with data file selection."""
    return render(request, 'net_maestro/index.html')


def analysis_page(request: HttpRequest) -> HttpResponse:
    """Render the analysis page with list of runs."""
    runs = Run.objects.all()
    return render(request, 'net_maestro/analysis.html', {'runs': runs})
