from collections import namedtuple
import logging
from struct import Struct
from typing import BinaryIO, Literal, Optional

import pandas as pd

# Struct configuration
ENDIAN = '@'

# Metadata
# TODO: Do not hardcode META_FORMAT; schema/versioned header if possible?
META_FORMAT = f'{ENDIAN}2i2d'
META_STRUCT = Struct(META_FORMAT)
META = namedtuple('META', 'flag sample_size virtual_time real_time')

# Payload structs
# TODO: Do not hardcode PE_FORMAT; schema/versioned header if possible?
# TODO: More explicit name for "PE"
PE_FORMAT = f'{ENDIAN}13I13f'  # TODO: Do not hardcode; consider schema-driven payload
PE_STRUCT = Struct(PE_FORMAT)
PE = namedtuple(
    'PE',
    'PE_ID events_processed events_aborted events_rolled_back total_rollbacks '
    'secondary_rollbacks fossil_collection_attempts pq_queue_size network_sends '
    'network_reads number_gvt pe_event_ties all_reduce efficiency network_read_time '
    'network_other_time gvt_time fossil_collect_time event_abort_time event_process_time '
    'pq_time rollback_time cancel_q_time avl_time buddy_time lz4_time',
)

# TODO: Do not hardcode KP_FORMAT; schema/versioned header if possible?
# More explicit name for "KP"
KP_FORMAT = f'{ENDIAN}9I2f'
KP_STRUCT = Struct(KP_FORMAT)
KP = namedtuple(
    'KP',
    'PE_ID KP_ID events_processed events_abort events_rolled_back total_rollbacks '
    'secondary_rollbacks network_sends network_reads time_ahead_gvt efficiency',
)

# TODO: Do not hardcode META_FORMAT; schema/versioned header if possible?
# More explicit name for "LP"
LP_FORMAT = f'{ENDIAN}8If'
LP_STRUCT = Struct(LP_FORMAT)
LP = namedtuple(
    'LP',
    'PE_ID KP_ID LP_ID events_processed events_abort events_rolled_back '
    'network_sends network_reads efficiency',
)


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

        self.pe_struct: Struct = PE_STRUCT
        self.pe_size: int = PE_STRUCT.size

        self.kp_struct: Struct = KP_STRUCT
        self.kp_size: int = KP_STRUCT.size

        self.lp_struct: Struct = LP_STRUCT
        self.lp_size: int = LP_STRUCT.size

        self._use_virtual_time: bool = True
        self._time_variable: Literal['virtual_time', 'real_time'] = 'virtual_time'

        self._pe_df: Optional[pd.DataFrame] = None
        self._kp_df: Optional[pd.DataFrame] = None
        self._lp_df: Optional[pd.DataFrame] = None
        self._min_time: Optional[float] = None
        self._max_time: Optional[float] = None

    def read(self) -> None:
        pe_list: list[pd.DataFrame] = []
        kp_list: list[pd.DataFrame] = []
        lp_list: list[pd.DataFrame] = []
        byte_pos = 0

        while byte_pos + self.metadata_size <= len(self.content):
            metadata_tuple = self.metadata_struct.unpack_from(self.content, byte_pos)
            byte_pos += self.metadata_size
            metadata = META._make(metadata_tuple)

            if metadata.sample_size == self.pe_size and (byte_pos + self.pe_size) <= len(
                self.content
            ):
                pe_tuple = self.pe_struct.unpack_from(self.content, byte_pos)
                byte_pos += self.pe_size
                pe_data = PE._make(pe_tuple)
                df = pd.DataFrame([pe_data])
                df['virtual_time'] = metadata.virtual_time
                df['real_time'] = metadata.real_time
                pe_list.append(df)
            elif metadata.sample_size == self.kp_size and (byte_pos + self.kp_size) <= len(
                self.content
            ):
                kp_tuple = self.kp_struct.unpack_from(self.content, byte_pos)
                byte_pos += self.kp_size
                kp_data = KP._make(kp_tuple)
                df = pd.DataFrame([kp_data])
                df['virtual_time'] = metadata.virtual_time
                df['real_time'] = metadata.real_time
                kp_list.append(df)
            elif metadata.sample_size == self.lp_size and (byte_pos + self.lp_size) <= len(
                self.content
            ):
                lp_tuple = self.lp_struct.unpack_from(self.content, byte_pos)
                byte_pos += self.lp_size
                lp_data = LP._make(lp_tuple)
                df = pd.DataFrame([lp_data])
                df['virtual_time'] = metadata.virtual_time
                df['real_time'] = metadata.real_time
                lp_list.append(df)
            else:
                remaining = len(self.content) - byte_pos
                logging.warning(
                    'Stopping parse due to invalid payload size: size=%d, remaining=%d',
                    metadata.sample_size,
                    remaining,
                )
                break

        self.pe_df = pd.concat(pe_list, ignore_index=True) if pe_list else pd.DataFrame()
        self.kp_df = pd.concat(kp_list, ignore_index=True) if kp_list else pd.DataFrame()
        self.lp_df = pd.concat(lp_list, ignore_index=True) if lp_list else pd.DataFrame()

        if not self.pe_engine_df.empty:
            self.min_time = float(self.pe_engine_df[self.time_variable].min())
            self.max_time = float(self.pe_engine_df[self.time_variable].max())

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
    def time_variable(self) -> Literal['virtual_time', 'real_time']:
        return self._time_variable

    @time_variable.setter
    def time_variable(self, var: Literal['virtual_time', 'real_time']) -> None:
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
        if self.pe_engine_df.empty:
            self._min_time = None
            self._max_time = None
            return

        self.min_time = float(self.pe_engine_df[self.time_variable].min())
        self.max_time = float(self.pe_engine_df[self.time_variable].max())

    @property
    def use_virtual_time(self) -> bool:
        return self._use_virtual_time

    @use_virtual_time.setter
    def use_virtual_time(self, flag: bool) -> None:
        self._use_virtual_time = flag
        self.time_variable = 'virtual_time' if flag else 'real_time'
        self.reset_time_range()
