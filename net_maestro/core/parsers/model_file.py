from __future__ import annotations

import logging
import struct
from struct import Struct
from typing import TYPE_CHECKING, NamedTuple

import pandas as pd

from .schema import ENDIAN, validate_time_columns

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# Metadata
META_FIELDS = ("lp_id", "kp_id", "pe_id", "virtual_time", "real_time", "sample_size", "flag")
META_FORMAT = f"{ENDIAN}QLLddii"
META_STRUCT = struct.Struct(META_FORMAT)


class META(NamedTuple):
    lp_id: int
    kp_id: int
    pe_id: int
    virtual_time: float
    real_time: float
    sample_size: int
    flag: int


# SimpleP2P model payload
SIMPLEP2P_FIELDS = (
    "component_id",
    "send_count",
    "send_bytes",
    "send_time",
    "receive_count",
    "receive_bytes",
    "receive_time",
)
SIMPLEP2P_FORMAT = f"{ENDIAN}Qlldlld"
SIMPLEP2P_STRUCT = struct.Struct(SIMPLEP2P_FORMAT)


class SimpleP2P(NamedTuple):
    component_id: int
    send_count: int
    send_bytes: int
    send_time: float
    receive_count: int
    receive_bytes: int
    receive_time: float


# Flag #3 is model data
FLAG_MODEL_DATA = 3

# Default Values
DEFAULT_TIME_KEY = "virtual_time"
ALT_TIME_KEY = "real_time"
TIME_COLUMNS = [DEFAULT_TIME_KEY, ALT_TIME_KEY]


class ModelFile:
    """Parser for model analysis Logical Process (LP) binary files."""

    def __init__(self, filename: Path) -> None:
        with filename.open("rb") as f:
            self.content: bytes = f.read()

        self.metadata_struct: Struct = META_STRUCT
        self.metadata_size: int = META_STRUCT.size

        # TODO: will need to figure out a way to not hardcode this
        self.simplep2p_struct: Struct = SIMPLEP2P_STRUCT
        self.simplep2p_size: int = SIMPLEP2P_STRUCT.size

        self._use_virtual_time: bool = True
        self._time_variable: str = DEFAULT_TIME_KEY

        self._simplep2p_df: pd.DataFrame | None = None
        self._min_time: float | None = None
        self._max_time: float | None = None

    def read(self) -> None:
        sample_list: list[pd.DataFrame] = []
        byte_pos = 0

        while byte_pos + self.metadata_size <= len(self.content):
            metadata_tuple = self.metadata_struct.unpack_from(self.content, byte_pos)
            byte_pos += self.metadata_size
            metadata = META(*metadata_tuple)

            if (
                metadata.flag == FLAG_MODEL_DATA
                and metadata.sample_size == self.simplep2p_size
                and (byte_pos + self.simplep2p_size) <= len(self.content)
            ):
                sp_tuple = self.simplep2p_struct.unpack_from(self.content, byte_pos)
                byte_pos += self.simplep2p_size
                sp_data = SimpleP2P(*sp_tuple)
                df = pd.DataFrame([sp_data])
                df["lp_id"] = metadata.lp_id
                df["virtual_time"] = metadata.virtual_time
                df["real_time"] = metadata.real_time
                sample_list.append(df)
            else:
                # Unknown payload size or flag
                remaining = len(self.content) - byte_pos
                logger.warning(
                    "Stopping parse due to invalid payload size: size=%d, remaining=%d",
                    metadata.sample_size,
                    remaining,
                )
                break

        self.simplep2p_df = validate_time_columns(
            pd.concat(sample_list, ignore_index=True), TIME_COLUMNS
        )
        if not self.simplep2p_df.empty:
            self.min_time = float(self.simplep2p_df[self.time_variable].min())
            self.max_time = float(self.simplep2p_df[self.time_variable].max())

    @property
    def max_time(self) -> float | None:
        return self._max_time

    @max_time.setter
    def max_time(self, time: float | None) -> None:
        self._max_time = time

    @property
    def min_time(self) -> float | None:
        return self._min_time

    @min_time.setter
    def min_time(self, time: float | None) -> None:
        self._min_time = time

    @property
    def time_variable(self) -> str:
        return self._time_variable

    @time_variable.setter
    def time_variable(self, var: str) -> None:
        self._time_variable = var

    @property
    def simplep2p_df(self) -> pd.DataFrame:
        if self._simplep2p_df is None:
            return pd.DataFrame()

        return self._simplep2p_df

    @simplep2p_df.setter
    def simplep2p_df(self, df: pd.DataFrame) -> None:
        self._simplep2p_df = df

    @property
    def network_df(self) -> pd.DataFrame:
        if self.simplep2p_df.empty or self.min_time is None or self.max_time is None:
            return pd.DataFrame()

        return self.simplep2p_df[
            (self.simplep2p_df[self.time_variable] >= self.min_time)
            & (self.simplep2p_df[self.time_variable] <= self.max_time)
        ]

    def reset_time_range(self) -> None:
        if self.simplep2p_df.empty:
            self.min_time = None
            self.max_time = None
            return

        self.min_time = float(self.simplep2p_df[self.time_variable].min())
        self.max_time = float(self.simplep2p_df[self.time_variable].max())

    @property
    def use_virtual_time(self) -> bool:
        return self._use_virtual_time

    @use_virtual_time.setter
    def use_virtual_time(self, flag: bool) -> None:
        self._use_virtual_time = flag
        self.time_variable = "virtual_time" if flag else "real_time"
        self.reset_time_range()
