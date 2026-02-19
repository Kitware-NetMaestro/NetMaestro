"""REST API endpoints for data file management and binary data parsing.

Provides endpoints for:
- Listing available data files in each category (simulations, events, models)
- Selecting which file to use for each category (stored in session)
- Parsing and returning binary data as JSON for visualization

Permissions:
- DEBUG mode: AllowAny (open access for development)
- Production: IsAuthenticated (requires login)

Note: We use AllowAny in DEBUG mode to simplify local development and testing,
avoiding the need to authenticate for every API request during development.
In production, IsAuthenticated ensures only logged-in users can access data endpoints.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from net_maestro.core.parsers.event_trace_file import EventFile
from net_maestro.core.parsers.model_file import ModelFile
from net_maestro.core.parsers.ross_binary_file import ROSSFile

if TYPE_CHECKING:
    import pandas as pd
    from rest_framework.request import Request

BASE_DIR = Path(settings.BASE_DIR)
DATA_DIR = BASE_DIR / 'data'

# Permission classes: open in DEBUG mode, authenticated in production
DATA_API_PERMISSION_CLASSES = (
    (AllowAny,) if bool(getattr(settings, 'DEBUG', False)) else (IsAuthenticated,)
)

# Default filenames to select if present (sample data)
_DEFAULT_FILES: dict[str, str] = {
    'models': 'esnet-model-inst-analysis-lps.bin',
    'events': 'esnet-model-inst-evtrace.bin',
    'simulations': 'ross-stats-gvt.bin',
}

# Session keys for storing currently selected file per category
_SESSION_KEYS: dict[str, str] = {
    'models': 'current_model_file',
    'events': 'current_event_file',
    'simulations': 'current_simulation_file',
}


def _list_files(*, subdir: str) -> list[str]:
    """List all files in the specified data subdirectory.

    Returns:
        Sorted list of filenames (not full paths)
    """
    directory = DATA_DIR / subdir
    if not directory.exists() or not directory.is_dir():
        return []
    return sorted([path.name for path in directory.iterdir() if path.is_file()])


def _get_selected_file(*, request: Request, subdir: str, available: list[str]) -> str | None:
    """Get the currently selected file for a category, with fallback logic.

    Selection priority:
    1. File stored in session (if still available)
    2. Default file from _DEFAULT_FILES (if present)
    3. First available file alphabetically
    4. None if no files available

    Updates session with the selected file.

    Returns:
        Selected filename or None if no files available
    """
    session_key = _SESSION_KEYS[subdir]
    selected = request.session.get(session_key)

    # Return session-stored file if still available
    if isinstance(selected, str) and selected in available:
        return selected

    # Fall back to default file if present
    default_name = _DEFAULT_FILES[subdir]
    if default_name in available:
        request.session[session_key] = default_name
        return default_name

    # Fall back to first available file
    first = available[0] if available else None
    if first is not None:
        request.session[session_key] = first
    return first


def _resolve_selected_path(
    *,
    request: Request,
    subdir: str,
    session_key: str,
    query_param: str,
) -> tuple[Path | None, str | None, str | None]:
    """Resolve a filename to an absolute path with security validation.

    Checks query params first, then falls back to session. Validates that the
    resolved path is a direct child of DATA_DIR/subdir to prevent path traversal.

    Returns:
        Tuple of (resolved_path, requested_name, error_message)
        - resolved_path: Absolute Path if valid, None otherwise
        - requested_name: Filename that was requested
        - error_message: Human-readable error if path is invalid
    """
    # Check query param first, then session
    requested_name = request.query_params.get(query_param)
    if not requested_name:
        session_name = request.session.get(session_key)
        requested_name = session_name if isinstance(session_name, str) else None

    if not requested_name:
        return None, None, None

    # Validate file exists
    candidate = DATA_DIR / subdir / requested_name
    if not candidate.exists() or not candidate.is_file():
        return None, requested_name, f'Missing file: {requested_name}'

    # Security check: prevent arbitrary path traversal
    if candidate.parent.resolve() != (DATA_DIR / subdir).resolve():
        return None, requested_name, 'Invalid file selection'

    return candidate, requested_name, None


def _df_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a pandas DataFrame to a list of record dictionaries.

    Returns:
        List of dictionaries, one per row, with column names as keys
    """
    return df.to_dict(orient='records')


class EventDataView(APIView):
    """API endpoint for parsing and returning event trace binary data.

    GET /api/v1/data/event?file=<filename>

    Returns event trace data as JSON with columns and records.
    Uses EventFile parser to read binary format.

    WARNING: Internal API - subject to change without notice.
    Do not build external integrations against this endpoint.
    """

    permission_classes = DATA_API_PERMISSION_CLASSES

    def get(self, request: Request) -> Response:
        """Parse and return event trace data from the selected binary file.

        Query params:
            file (optional): Specific filename to parse. Falls back to session selection.

        Returns:
            JSON with 'file', 'columns', and 'data' keys, or 404 if file not found
        """
        # Ensure a file is selected (with fallback to defaults/first available)
        available = _list_files(subdir='events')
        _get_selected_file(request=request, subdir='events', available=available)

        # Now resolve the path (either from query param or the selected file)
        path, requested_name, error = _resolve_selected_path(
            request=request,
            subdir='events',
            session_key='current_event_file',
            query_param='file',
        )
        if path is None:
            detail = error or 'No file selected'
            if requested_name:
                detail = f'{detail} ({requested_name})'
            return Response({'detail': detail}, status=404)

        # Parse binary file and return network DataFrame as JSON
        event_file = EventFile(str(path))
        try:
            event_file.read()
            df = event_file.network_df
            return Response(
                {
                    'file': path.name,
                    'columns': list(df.columns),
                    'data': _df_records(df),
                }
            )
        finally:
            event_file.close()


class ModelDataView(APIView):
    """API endpoint for parsing and returning model analysis binary data.

    GET /api/v1/data/model?file=<filename>

    Returns model data as JSON with columns and records.
    Uses ModelFile parser to read binary format.

    WARNING: Internal API - subject to change without notice.
    Do not build external integrations against this endpoint.
    """

    permission_classes = DATA_API_PERMISSION_CLASSES

    def get(self, request: Request) -> Response:
        """Parse and return model data from the selected binary file.

        Query params:
            file (optional): Specific filename to parse. Falls back to session selection.

        Returns:
            JSON with 'file', 'columns', and 'data' keys, or 404 if file not found
        """
        # Ensure a file is selected (with fallback to defaults/first available)
        available = _list_files(subdir='models')
        _get_selected_file(request=request, subdir='models', available=available)

        # Now resolve the path (either from query param or the selected file)
        path, requested_name, error = _resolve_selected_path(
            request=request,
            subdir='models',
            session_key='current_model_file',
            query_param='file',
        )
        if path is None:
            detail = error or 'No file selected'
            if requested_name:
                detail = f'{detail} ({requested_name})'
            return Response({'detail': detail}, status=404)

        # Parse binary file and return network DataFrame as JSON
        model_file = ModelFile(str(path))
        try:
            model_file.read()
            df = model_file.network_df
            return Response(
                {
                    'file': path.name,
                    'columns': list(df.columns),
                    'data': _df_records(df),
                }
            )
        finally:
            model_file.close()


class RossDataView(APIView):
    """API endpoint for parsing and returning ROSS simulation binary data.

    GET /api/v1/data/ross?file=<filename>

    Returns ROSS processing element data as JSON with columns and records.
    Uses ROSSFile parser to read binary format.

    WARNING: Internal API - subject to change without notice.
    Do not build external integrations against this endpoint.
    """

    permission_classes = DATA_API_PERMISSION_CLASSES

    def get(self, request: Request) -> Response:
        """Parse and return ROSS simulation data from the selected binary file.

        Query params:
            file (optional): Specific filename to parse. Falls back to session selection.

        Returns:
            JSON with 'file', 'columns', and 'data' keys, or 404 if file not found
        """
        # Ensure a file is selected (with fallback to defaults/first available)
        available = _list_files(subdir='simulations')
        _get_selected_file(request=request, subdir='simulations', available=available)

        # Now resolve the path (either from query param or the selected file)
        path, requested_name, error = _resolve_selected_path(
            request=request,
            subdir='simulations',
            session_key='current_simulation_file',
            query_param='file',
        )
        if path is None:
            detail = error or 'No file selected'
            if requested_name:
                detail = f'{detail} ({requested_name})'
            return Response({'detail': detail}, status=404)

        # Parse binary file and return PE engine DataFrame as JSON
        ross_file = ROSSFile(str(path))
        try:
            ross_file.read()
            df = ross_file.pe_engine_df
            return Response(
                {
                    'file': path.name,
                    'columns': list(df.columns),
                    'data': _df_records(df),
                }
            )
        finally:
            ross_file.close()


class DataFilesView(APIView):
    """API endpoint for listing available data files and current selections.

    GET /api/v1/data/files

    Returns all available files in each category plus the currently selected
    file for each category (from session).

    WARNING: Internal API - subject to change without notice.
    Do not build external integrations against this endpoint.
    """

    permission_classes = DATA_API_PERMISSION_CLASSES

    def get(self, request: Request) -> Response:
        """List available files and current selections for all categories.

        Returns:
            JSON with 'files' (available files per category) and 'selected'
            (currently selected file per category)
        """
        # List available files in each category
        simulations = _list_files(subdir='simulations')
        events = _list_files(subdir='events')
        models = _list_files(subdir='models')

        # Determine selected file for each category (updates session if needed)
        selected_simulation = _get_selected_file(
            request=request,
            subdir='simulations',
            available=simulations,
        )
        selected_event = _get_selected_file(
            request=request,
            subdir='events',
            available=events,
        )
        selected_model = _get_selected_file(
            request=request,
            subdir='models',
            available=models,
        )

        return Response(
            {
                'files': {
                    'simulations': simulations,
                    'events': events,
                    'models': models,
                },
                'selected': {
                    'simulations': selected_simulation,
                    'events': selected_event,
                    'models': selected_model,
                },
            }
        )


class SelectDataFileView(APIView):
    """API endpoint for updating the selected file for a category.

    POST /api/v1/data/select
    Body: {"category": "simulations|events|models", "file": "filename.bin"}

    Updates the session to remember which file is selected for the given category.

    WARNING: Internal API - subject to change without notice.
    Do not build external integrations against this endpoint.
    """

    permission_classes = DATA_API_PERMISSION_CLASSES

    def post(self, request: Request) -> Response:
        """Update the selected file for a category in the session.

        Request body:
            category: One of 'simulations', 'events', or 'models'
            file: Filename to select (must exist in the category directory)

        Returns:
            JSON with updated selection, or 400 if invalid category/file
        """
        category = request.data.get('category')
        file_name = request.data.get('file')

        # Validate category
        if category not in _SESSION_KEYS:
            return Response({'detail': 'Invalid category'}, status=400)

        # Validate file name
        if not isinstance(file_name, str) or not file_name:
            return Response({'detail': 'Invalid file'}, status=400)

        # Verify file exists in the category directory
        available = _list_files(subdir=str(category))
        if file_name not in available:
            return Response({'detail': 'Invalid file'}, status=400)

        # Update session with selected file
        request.session[_SESSION_KEYS[str(category)]] = file_name
        return Response({'selected': {str(category): file_name}})
