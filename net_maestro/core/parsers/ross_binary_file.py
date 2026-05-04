from __future__ import annotations

from collections import defaultdict
from enum import Enum
import logging
from pathlib import Path
from struct import Struct
from typing import TYPE_CHECKING, Any, NamedTuple

import pandas as pd

from .schema import ENDIAN, validate_time_columns

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)

# Metadata
META_FORMAT = f"{ENDIAN}2i2d"
META_STRUCT = Struct(META_FORMAT)
META_FIELDS = ("flag", "sample_size", "virtual_time", "real_time")


class META(NamedTuple):
    flag: int
    sample_size: int
    virtual_time: float
    real_time: float


class RecordType(Enum):
    PE = "pe"
    KP = "kp"
    LP = "lp"


# Payload structs
PE_FORMAT = f"{ENDIAN}13I13f"
PE_STRUCT = Struct(PE_FORMAT)
PE_FIELDS = (
    "PE_ID",
    "events_processed",
    "events_aborted",
    "events_rolled_back",
    "total_rollbacks",
    "secondary_rollbacks",
    "fossil_collection_attempts",
    "pq_queue_size",
    "network_sends",
    "network_reads",
    "number_gvt",
    "pe_event_ties",
    "all_reduce",
    "efficiency",
    "network_read_time",
    "network_other_time",
    "gvt_time",
    "fossil_collect_time",
    "event_abort_time",
    "event_process_time",
    "pq_time",
    "rollback_time",
    "cancel_q_time",
    "avl_time",
    "buddy_time",
    "lz4_time",
)


KP_FORMAT = f"{ENDIAN}9I2f"
KP_STRUCT = Struct(KP_FORMAT)
KP_FIELDS = (
    "PE_ID",
    "KP_ID",
    "events_processed",
    "events_abort",
    "events_rolled_back",
    "total_rollbacks",
    "secondary_rollbacks",
    "network_sends",
    "network_reads",
    "time_ahead_gvt",
    "efficiency",
)

# More explicit name for "LP"
LP_FORMAT = f"{ENDIAN}8If"
LP_STRUCT = Struct(LP_FORMAT)
LP_FIELDS = (
    "PE_ID",
    "KP_ID",
    "LP_ID",
    "events_processed",
    "events_abort",
    "events_rolled_back",
    "network_sends",
    "network_reads",
    "efficiency",
)

PAYLOAD_MAP: dict[int, tuple[RecordType, Struct, tuple[str, ...]]] = {
    PE_STRUCT.size: (RecordType.PE, PE_STRUCT, PE_FIELDS),
    KP_STRUCT.size: (RecordType.KP, KP_STRUCT, KP_FIELDS),
    LP_STRUCT.size: (RecordType.LP, LP_STRUCT, LP_FIELDS),
}


# Default Values
DEFAULT_TIME_KEY = "virtual_time"
ALT_TIME_KEY = "real_time"
TIME_COLUMNS = [DEFAULT_TIME_KEY, ALT_TIME_KEY]


class ROSSFile:
    """Parser for ROSS engine binary stats (PE/KP/LP records).

    Each record starts with a fixed-size header (flag, sample_size, times)
    followed by a payload whose size determines the structure (PE/KP/LP).
    """

    def __init__(self, source: Path | bytes) -> None:
        if isinstance(source, Path):
            with source.open("rb") as f:
                self.content = f.read()
        else:
            self.content = source

        self._use_virtual_time: bool = True
        self._time_variable: str = DEFAULT_TIME_KEY

        self._pe_df: pd.DataFrame | None = None
        self._kp_df: pd.DataFrame | None = None
        self._lp_df: pd.DataFrame | None = None
        self._min_time: float | None = None
        self._max_time: float | None = None

    def parse_simulation_records(self) -> Generator[tuple[RecordType, dict[str, Any]]]:
        byte_pos = 0

        while byte_pos + META_STRUCT.size <= len(self.content):
            metadata_tuple = META_STRUCT.unpack_from(self.content, byte_pos)
            byte_pos += META_STRUCT.size
            metadata = dict(zip(META_FIELDS, metadata_tuple, strict=False))
            record_data = None

            payload_size = metadata["sample_size"]

            if payload_size not in PAYLOAD_MAP:
                remaining = len(self.content) - byte_pos
                logger.warning(
                    "Stopping parse due to invalid payload size: size=%d, remaining=%d",
                    payload_size,
                    remaining,
                )
                break

            record_type, struct, fields = PAYLOAD_MAP[payload_size]

            values = struct.unpack_from(self.content, byte_pos)
            record_data = dict(zip(fields, values, strict=False))
            record_data["virtual_time"] = metadata["virtual_time"]
            record_data["real_time"] = metadata["real_time"]
            byte_pos += struct.size

            yield record_type, record_data

    def read(self) -> None:
        record_lists: dict[RecordType, list[pd.DataFrame]] = defaultdict(list)

        for record_type, record_data in self.parse_simulation_records():
            record_dataframe = pd.DataFrame([record_data])

            record_lists[record_type].append(record_dataframe)

        # TODO: review for more efficient approach. Perhaps a helper function here.
        self.pe_df = validate_time_columns(
            pd.concat(record_lists[RecordType.PE], ignore_index=True)
            if record_lists[RecordType.PE]
            else pd.DataFrame(),
            TIME_COLUMNS,
        )
        self.kp_df = validate_time_columns(
            pd.concat(record_lists[RecordType.KP], ignore_index=True)
            if record_lists[RecordType.KP]
            else pd.DataFrame(),
            TIME_COLUMNS,
        )
        self.lp_df = validate_time_columns(
            pd.concat(record_lists[RecordType.LP], ignore_index=True)
            if record_lists[RecordType.LP]
            else pd.DataFrame(),
            TIME_COLUMNS,
        )

        if not self.pe_df.empty:
            self.min_time = float(self.pe_df[self.time_variable].min())
            self.max_time = float(self.pe_df[self.time_variable].max())

    @property
    def max_time(self) -> float | None:
        return self._max_time

    @max_time.setter
    def max_time(self, time: float) -> None:
        self._max_time = time

    @property
    def min_time(self) -> float | None:
        return self._min_time

    @min_time.setter
    def min_time(self, time: float) -> None:
        self._min_time = time

    @property
    def time_variable(self) -> str:
        return self._time_variable

    @time_variable.setter
    def time_variable(self, var: str) -> None:
        self._time_variable = var

    @property
    def pe_df(self) -> pd.DataFrame:
        if self._pe_df is None:
            return pd.DataFrame()

        return self._pe_df

    @pe_df.setter
    def pe_df(self, df: pd.DataFrame) -> None:
        self._pe_df = df

    @property
    def kp_df(self) -> pd.DataFrame:
        if self._kp_df is None:
            return pd.DataFrame()

        return self._kp_df

    @kp_df.setter
    def kp_df(self, df: pd.DataFrame) -> None:
        self._kp_df = df

    @property
    def lp_df(self) -> pd.DataFrame:
        if self._lp_df is None:
            return pd.DataFrame()

        return self._lp_df

    @lp_df.setter
    def lp_df(self, df: pd.DataFrame) -> None:
        self._lp_df = df

    @property
    def pe_engine_df(self) -> pd.DataFrame:
        if self.pe_df.empty or self.min_time is None or self.max_time is None:
            return pd.DataFrame()

        return self.pe_df[
            (self.pe_df[self.time_variable] >= self.min_time)
            & (self.pe_df[self.time_variable] <= self.max_time)
        ]

    def reset_time_range(self) -> None:
        if self.pe_df.empty:
            self._min_time = None
            self._max_time = None
            return

        self.min_time = float(self.pe_df[self.time_variable].min())
        self.max_time = float(self.pe_df[self.time_variable].max())

    @property
    def use_virtual_time(self) -> bool:
        return self._use_virtual_time

    @use_virtual_time.setter
    def use_virtual_time(self, flag: bool) -> None:
        self._use_virtual_time = flag
        self.time_variable = "virtual_time" if flag else "real_time"
        self.reset_time_range()
