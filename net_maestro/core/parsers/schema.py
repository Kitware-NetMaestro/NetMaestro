from __future__ import annotations

from contextlib import suppress
import struct
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

# Default endianness
ENDIAN: str = '@'
LITTLE_ENDIAN = '<'
BIG_ENDIAN = '>'


def infer_endian(
    make_header_format: Callable[[str], str],
    sample_size_index: int,
    content: bytes,
    known_payload_sizes: set[int],
) -> str:
    """Try to infer endianness by decoding the header.

    Attempt both little-endian and big-endian and accept the one whose sample_size field
    matches a known payload size and seems plausible given the remaining bytes.
    Returns the detected endianness or falls back to ENDIAN.
    """
    if not content:
        return ENDIAN

    for endian in (LITTLE_ENDIAN, BIG_ENDIAN):
        fmt = make_header_format(endian)
        hdr = struct.Struct(fmt)
        if len(content) < hdr.size:
            continue

        # Suppress *EXPECTED* errors only. Fall through and try the next option on failure.
        with suppress(struct.error, IndexError, ValueError):
            values = hdr.unpack_from(content, 0)
            sample_size = int(values[sample_size_index])
            remaining = len(content) - hdr.size
            if validate_sample_size(sample_size, remaining, known_payload_sizes):
                return endian

    return ENDIAN


def validate_sample_size(sample_size: int, remaining: int, known: set[int]) -> bool:
    """Check that sample_size extracted from header is valid."""
    if sample_size <= 0:
        return False
    if sample_size not in known:
        return False
    return sample_size <= remaining


def validate_time_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    """Return a filtered copy where the given time columns are finite numeric values."""
    if df.empty:
        return df

    mask = pd.Series(data=True, index=df.index)
    for col in columns:
        if col in df.columns:
            # Convert column to numeric; non-numeric becomes "NaN"
            vals = pd.to_numeric(df[col], errors='coerce')
            # Only finite values are "True"
            mask &= pd.Series(np.isfinite(vals), index=df.index)
    return df.loc[mask]
