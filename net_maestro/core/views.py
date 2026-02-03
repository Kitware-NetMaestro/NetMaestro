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


def home(request: HttpRequest) -> HttpResponse:
    """Render the main application page with data file selection."""
    return render(request, 'net_maestro/index.html')
