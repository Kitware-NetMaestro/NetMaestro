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

from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie
def home(request: HttpRequest) -> HttpResponse:
    """Render the main application page with data file selection.

    Displays the main UI with available data files and current selections.
    File selection is handled via AJAX POST requests to /api/v1/data/select.

    File selection uses session state with fallback logic:
    1. Previously selected file (from session)
    2. First available file alphabetically

    Args:
        request: HTTP request object with session

    Returns:
        Rendered HTML response with context containing available files
        and current selections for each category
    """
    base_dir = Path(settings.BASE_DIR)
    data_dir = base_dir / 'data'

    # Session keys for storing selected file per category
    session_keys = {
        'models': 'current_model_file',
        'events': 'current_event_file',
        'simulations': 'current_simulation_file',
    }

    def list_files(subdir: str) -> list[str]:
        """List all files in a data subdirectory.

        Args:
            subdir: Subdirectory name (events, models, or simulations)

        Returns:
            Sorted list of filenames (not full paths)
        """
        directory = data_dir / subdir
        if not directory.exists() or not directory.is_dir():
            return []
        return sorted([path.name for path in directory.iterdir() if path.is_file()])

    available = {subdir: list_files(subdir) for subdir in ['simulations', 'events', 'models']}
    selected_by_subdir: dict[str, str | None] = {}

    for subdir in ['simulations', 'events', 'models']:
        selected = request.session.get(session_keys[subdir])
        # Try to use session-stored selection if available
        if isinstance(selected, str) and selected in available[subdir]:
            selected_by_subdir[subdir] = selected
            continue

        # If not available, use first available file alphabetically
        selected_by_subdir[subdir] = available[subdir][0] if available[subdir] else None
        if selected_by_subdir[subdir] is not None:
            request.session[session_keys[subdir]] = selected_by_subdir[subdir]

    # Build template context with available files and selections
    context = {
        'simulation_files': available['simulations'],
        'event_files': available['events'],
        'model_files': available['models'],
        'selected_simulation_file': selected_by_subdir['simulations'],
        'selected_event_file': selected_by_subdir['events'],
        'selected_model_file': selected_by_subdir['models'],
    }
    return render(request, 'net_maestro/index.html', context)
