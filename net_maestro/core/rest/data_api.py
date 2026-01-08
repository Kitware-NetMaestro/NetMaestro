from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from django.conf import settings
import pandas as pd
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from net_maestro.core.parsers.event_trace_file import EventFile
from net_maestro.core.parsers.model_file import ModelFile
from net_maestro.core.parsers.ross_binary_file import ROSSFile

BASE_DIR = Path(settings.BASE_DIR)
DATA_DIR = BASE_DIR / 'data'


# Build possible paths under the data directory to look for a file.
def _possible_paths(fname: str, subdir: str | None = None) -> List[Path]:
    paths: List[Path] = [DATA_DIR / fname]
    if subdir:
        paths.append(DATA_DIR / subdir / fname)
    return paths


# Convert a DataFrame to list-of-dicts (records)
def _df_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    return df.to_dict(orient='records')


class EventDataView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        fname = 'esnet-model-inst-evtrace.bin'
        path: Path | None = None
        for next_path in _possible_paths(fname, 'events'):
            if next_path.exists():
                path = next_path
                break
        if path is None:
            return Response({'detail': f'Missing file: {fname}'}, status=404)

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
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        fname = 'esnet-model-inst-analysis-lps.bin'
        path: Path | None = None
        for next_path in _possible_paths(fname, 'models'):
            if next_path.exists():
                path = next_path
                break
        if path is None:
            return Response({'detail': f'Missing file: {fname}'}, status=404)

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
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        fname = 'ross-stats-gvt.bin'
        path: Path | None = None
        for next_path in _possible_paths(fname, 'simulations'):
            if next_path.exists():
                path = next_path
                break
        if path is None:
            return Response({'detail': f'Missing file: {fname}'}, status=404)

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
