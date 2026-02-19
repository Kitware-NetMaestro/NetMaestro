from __future__ import annotations

import logging
import struct
from struct import Struct
from typing import BinaryIO, NamedTuple

import pandas as pd

from .schema import ENDIAN, validate_time_columns

logger = logging.getLogger(__name__)

# Metadata
META_FIELDS = ('flag', 'sample_size', 'virtual_time', 'real_time')
META_FORMAT = f'{ENDIAN}2i2d'
META_STRUCT = struct.Struct(META_FORMAT)


class META(NamedTuple):
    flag: int
    sample_size: int
    virtual_time: float
    real_time: float


# Payload structs
PE_FORMAT = f'{ENDIAN}13I13f'
PE_STRUCT = struct.Struct(PE_FORMAT)
PE_FIELDS = (
    'PE_ID',
    'events_processed',
    'events_aborted',
    'events_rolled_back',
    'total_rollbacks',
    'secondary_rollbacks',
    'fossil_collection_attempts',
    'pq_queue_size',
    'network_sends',
    'network_reads',
    'number_gvt',
    'pe_event_ties',
    'all_reduce',
    'efficiency',
    'network_read_time',
    'network_other_time',
    'gvt_time',
    'fossil_collect_time',
    'event_abort_time',
    'event_process_time',
    'pq_time',
    'rollback_time',
    'cancel_q_time',
    'avl_time',
    'buddy_time',
    'lz4_time',
)


class PE(NamedTuple):
    PE_ID: int
    events_processed: int
    events_aborted: int
    events_rolled_back: int
    total_rollbacks: int
    secondary_rollbacks: int
    fossil_collection_attempts: int
    pq_queue_size: int
    network_sends: int
    network_reads: int
    number_gvt: int
    pe_event_ties: int
    all_reduce: int
    efficiency: float
    network_read_time: float
    network_other_time: float
    gvt_time: float
    fossil_collect_time: float
    event_abort_time: float
    event_process_time: float
    pq_time: float
    rollback_time: float
    cancel_q_time: float
    avl_time: float
    buddy_time: float
    lz4_time: float


KP_FORMAT = f'{ENDIAN}9I2f'
KP_STRUCT = struct.Struct(KP_FORMAT)
KP_FIELDS = (
    'PE_ID',
    'KP_ID',
    'events_processed',
    'events_abort',
    'events_rolled_back',
    'total_rollbacks',
    'secondary_rollbacks',
    'network_sends',
    'network_reads',
    'time_ahead_gvt',
    'efficiency',
)


class KP(NamedTuple):
    PE_ID: int
    KP_ID: int
    events_processed: int
    events_abort: int
    events_rolled_back: int
    total_rollbacks: int
    secondary_rollbacks: int
    network_sends: int
    network_reads: int
    time_ahead_gvt: float
    efficiency: float


# More explicit name for "LP"
LP_FORMAT = f'{ENDIAN}8If'
LP_STRUCT = struct.Struct(LP_FORMAT)
LP_FIELDS = (
    'PE_ID',
    'KP_ID',
    'LP_ID',
    'events_processed',
    'events_abort',
    'events_rolled_back',
    'network_sends',
    'network_reads',
    'efficiency',
)


class LP(NamedTuple):
    PE_ID: int
    KP_ID: int
    LP_ID: int
    events_processed: int
    events_abort: int
    events_rolled_back: int
    network_sends: int
    network_reads: int
    efficiency: float


# Default Values
DEFAULT_TIME_KEY = 'virtual_time'
ALT_TIME_KEY = 'real_time'
TIME_COLUMNS = [DEFAULT_TIME_KEY, ALT_TIME_KEY]


class ROSSFile:
    """Parser for ROSS engine binary stats (PE/KP/LP records).

    Each record starts with a fixed-size header (flag, sample_size, times)
    followed by a payload whose size determines the structure (PE/KP/LP).
    """

    def __init__(self, filename: str) -> None:
        self.f: BinaryIO = open(filename, 'rb')
        self.content: bytes = self.f.read()

        self.metadata_struct: Struct = META_STRUCT
        self.metadata_size: int = META_STRUCT.size

        self._proc_elem_struct = PE_STRUCT
        self._proc_elem_size = PE_STRUCT.size

        self._kernel_proc_struct = KP_STRUCT
        self._kernel_proc_size = KP_STRUCT.size

        self.lp_struct: Struct = LP_STRUCT
        self.lp_size: int = LP_STRUCT.size

        self._use_virtual_time: bool = True
        self._time_variable: str = DEFAULT_TIME_KEY

        self._pe_df: pd.DataFrame | None = None
        self._kp_df: pd.DataFrame | None = None
        self._lp_df: pd.DataFrame | None = None
        self._min_time: float | None = None
        self._max_time: float | None = None

    def read(self) -> None:
        pe_list: list[pd.DataFrame] = []
        kp_list: list[pd.DataFrame] = []
        lp_list: list[pd.DataFrame] = []
        byte_pos = 0

        while byte_pos + self.metadata_size <= len(self.content):
            metadata_tuple = self.metadata_struct.unpack_from(self.content, byte_pos)
            byte_pos += self.metadata_size
            metadata = META(*metadata_tuple)

            if metadata.sample_size == self._proc_elem_size and (
                byte_pos + self._proc_elem_size
            ) <= len(self.content):
                pe_tuple = self._proc_elem_struct.unpack_from(self.content, byte_pos)
                byte_pos += self._proc_elem_size
                pe_data = PE(*pe_tuple)
                df = pd.DataFrame([pe_data])
                df['virtual_time'] = metadata.virtual_time
                df['real_time'] = metadata.real_time
                pe_list.append(df)
            elif metadata.sample_size == self._kernel_proc_size and (
                byte_pos + self._kernel_proc_size
            ) <= len(self.content):
                kp_tuple = self._kernel_proc_struct.unpack_from(self.content, byte_pos)
                byte_pos += self._kernel_proc_size
                kp_data = KP(*kp_tuple)
                df = pd.DataFrame([kp_data])
                df['virtual_time'] = metadata.virtual_time
                df['real_time'] = metadata.real_time
                kp_list.append(df)
            elif metadata.sample_size == self.lp_size and (byte_pos + self.lp_size) <= len(
                self.content
            ):
                lp_tuple = self.lp_struct.unpack_from(self.content, byte_pos)
                byte_pos += self.lp_size
                lp_data = LP(*lp_tuple)
                df = pd.DataFrame([lp_data])
                df['virtual_time'] = metadata.virtual_time
                df['real_time'] = metadata.real_time
                lp_list.append(df)
            else:
                remaining = len(self.content) - byte_pos
                logger.warning(
                    'Stopping parse due to invalid payload size: size=%d, remaining=%d',
                    metadata.sample_size,
                    remaining,
                )
                break

        self.pe_df = validate_time_columns(
            pd.concat(pe_list, ignore_index=True) if pe_list else pd.DataFrame(), TIME_COLUMNS
        )
        self.kp_df = validate_time_columns(
            pd.concat(kp_list, ignore_index=True) if kp_list else pd.DataFrame(), TIME_COLUMNS
        )
        self.lp_df = validate_time_columns(
            pd.concat(lp_list, ignore_index=True) if lp_list else pd.DataFrame(), TIME_COLUMNS
        )

        if not self.pe_df.empty:
            self.min_time = float(self.pe_df[self.time_variable].min())
            self.max_time = float(self.pe_df[self.time_variable].max())

    def close(self) -> None:
        self.f.close()

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
        self.time_variable = 'virtual_time' if flag else 'real_time'
        self.reset_time_range()
