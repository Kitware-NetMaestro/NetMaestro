from __future__ import annotations

import struct
from typing import Any, Callable, Optional, Protocol

import pandas as pd


class HeaderTuple(Protocol):
    """Typing protocol for consistent access when parsing binary headers

    Used only for type checking. Defines the minimal interface expected from a header: integer
    indexing. This means that accessing any tuple-like object (e.g., plain tuple, namedtuple)
    matches this Protocol.
    """

    # Method bodies are intentionally empty. We're describing interface shape, not behavior.
    def __getitem__(self, key: int) -> Any:
        pass


ParseResult = tuple[int, Optional[pd.DataFrame], Optional[str], Optional[list[str]]]
PayloadHandler = Callable[[bytes, int, HeaderTuple], ParseResult]


class BaseBinaryReader:
    """Generic binary reader.

    Subclasses must provide a header struct and a mapping of payload sizes to
    handler functions.
    """

    def __init__(
        self,
        filename: str,
        header_struct: struct.Struct,
        sample_size_index: int,
        payloads: dict[int, PayloadHandler],
    ) -> None:
        self.f = open(filename, 'rb')
        self.content: bytes = self.f.read()
        self.header_struct = header_struct
        self.sample_size_index = sample_size_index
        self.payloads = payloads

    def close(self) -> None:
        self.f.close()

    def read(self) -> dict[str, pd.DataFrame]:
        frames: dict[str, list[pd.DataFrame]] = {}
        offset = 0
        n = len(self.content)

        while offset < n:
            if offset + self.header_struct.size > n:
                break

            header_tuple = self.header_struct.unpack_from(self.content, offset)
            offset += self.header_struct.size
            sample_size = int(header_tuple[self.sample_size_index])
            handler = self.payloads.get(sample_size)
            if handler is None:
                break

            new_offset, df, label, _time_cols = handler(self.content, offset, header_tuple)
            offset = new_offset
            if df is not None and label is not None:
                frames.setdefault(label, []).append(df)

        return {k: pd.concat(v) if v else pd.DataFrame() for k, v in frames.items()}
