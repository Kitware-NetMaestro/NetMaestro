from collections import namedtuple
import logging
from struct import Struct
from typing import BinaryIO, Literal, Optional

import pandas as pd

# Struct configuration
# Default endianness
ENDIAN = '@'
# Metadata
# TODO: Do not hardcode META_FORMAT; schema/versioned header if possible?
META_FORMAT = f'{ENDIAN}QLLddii'
META_STRUCT = Struct(META_FORMAT)
META = namedtuple(
    'META',
    (
        'lp_id',
        'kp_id',
        'pe_id',
        'virtual_time',
        'real_time',
        'sample_size',
        'flag',
    ),
)

# SimpleP2P model payload
SIMPLEP2P_FORMAT = f'{ENDIAN}Qlldlld'  # TODO: Do not hardcode; consider schema-driven payload
SIMPLEP2P_STRUCT = Struct(SIMPLEP2P_FORMAT)
SimpleP2P = namedtuple(
    'SimpleP2P',
    (
        'component_id',
        'send_count',
        'send_bytes',
        'send_time',
        'receive_count',
        'receive_bytes',
        'receive_time',
    ),
)

# Flag "3" is model data
FLAG_MODEL_DATA = 3  # TODO: Do not hardcode; derive from schema/const map


# NOTE: This actually reads the analysis "lps" files, which may include engine data as
# well, if collected.
class ModelFile:
    """Parser for model analysis Logical Process (LP) binary files."""

    def __init__(self, filename: str) -> None:
        self.f: BinaryIO = open(filename, 'rb')
        self.content: bytes = self.f.read()

        self.metadata_struct: Struct = META_STRUCT
        self.metadata_size: int = META_STRUCT.size

        # TODO: will need to figure out a way to not hardcode this
        self.simplep2p_struct: Struct = SIMPLEP2P_STRUCT
        self.simplep2p_size: int = SIMPLEP2P_STRUCT.size

        self._use_virtual_time: bool = True
        self._time_variable: Literal['virtual_time', 'real_time'] = 'virtual_time'

        self._simplep2p_df: Optional[pd.DataFrame] = None
        self._min_time: Optional[float] = None
        self._max_time: Optional[float] = None

    def read(self) -> None:
        sample_list: list[pd.DataFrame] = []
        byte_pos = 0

        while byte_pos + self.metadata_size <= len(self.content):
            metadata_tuple = self.metadata_struct.unpack_from(self.content, byte_pos)
            byte_pos += self.metadata_size
            metadata = META._make(metadata_tuple)

            if (
                metadata.flag == FLAG_MODEL_DATA
                and metadata.sample_size == self.simplep2p_size
                and (byte_pos + self.simplep2p_size) <= len(self.content)
            ):
                sp_tuple = self.simplep2p_struct.unpack_from(self.content, byte_pos)
                byte_pos += self.simplep2p_size
                sp_data = SimpleP2P._make(sp_tuple)
                df = pd.DataFrame([sp_data])
                df['lp_id'] = metadata.lp_id
                df['virtual_time'] = metadata.virtual_time
                df['real_time'] = metadata.real_time
                sample_list.append(df)
            else:
                # Unknown payload size or flag
                remaining = len(self.content) - byte_pos
                logging.warning(
                    'Stopping parse due to invalid payload size: size=%d, remaining=%d',
                    metadata.sample_size,
                    remaining,
                )
                break

        self.simplep2p_df = pd.concat(sample_list, ignore_index=True)
        self.min_time = float(self.simplep2p_df[self.time_variable].min())
        self.max_time = float(self.simplep2p_df[self.time_variable].max())

    def close(self) -> None:
        self.f.close()

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
    def time_variable(self) -> Literal['virtual_time', 'real_time']:
        return self._time_variable

    @time_variable.setter
    def time_variable(self, var: Literal['virtual_time', 'real_time']) -> None:
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
        self.time_variable = 'virtual_time' if flag else 'real_time'
        self.reset_time_range()
