from collections import namedtuple
import logging
from struct import Struct
from typing import BinaryIO, Literal, Optional

import pandas as pd

# Struct configuration
ENDIAN = '@'

# Metadata
# TODO: Do not hardcode META_FORMAT; schema/versioned header if possible?
META_FORMAT = f'{ENDIAN}IIfffI'
META_STRUCT = Struct(META_FORMAT)
META = namedtuple(
    'META',
    (
        'source_lp',
        'dest_lp',
        'virtual_send',
        'virtual_receive',
        'real_times',
        'sample_size',
    ),
)

# SimpleP2P payload
# TODO: Do not hardcode; schema-driven payload instead?
SIMPLEP2P_FORMAT = f'{ENDIAN}i'
SIMPLEP2P_STRUCT = Struct(SIMPLEP2P_FORMAT)
SimpleP2P = namedtuple('SimpleP2P', ('event_type',))


class EventFile:
    """Parser for event-trace binary files.

    Each record consists of a fixed-size metadata header followed by a payload.
    The header's sample_size selects the payload layout.
    """

    def __init__(self, filename: str) -> None:
        self.f: BinaryIO = open(filename, 'rb')
        self.content: bytes = self.f.read()

        self.metadata_struct: Struct = META_STRUCT
        self.metadata_size: int = META_STRUCT.size

        # TODO: will need to figure out a way to not hardcode this
        self.simplep2p_struct: Struct = SIMPLEP2P_STRUCT
        self.simplep2p_size: int = SIMPLEP2P_STRUCT.size

        self._use_send_time: bool = True
        self._time_variable: Literal['virtual_send', 'virtual_receive'] = 'virtual_send'

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

            if metadata.sample_size == self.simplep2p_size and (
                byte_pos + self.simplep2p_size <= len(self.content)
            ):
                sp_tuple = self.simplep2p_struct.unpack_from(self.content, byte_pos)
                byte_pos += self.simplep2p_size
                sp_data = SimpleP2P._make(sp_tuple)
                df = pd.DataFrame([sp_data])
                df['source_lp'] = metadata.source_lp
                df['dest_lp'] = metadata.dest_lp
                df['virtual_send'] = metadata.virtual_send
                df['virtual_receive'] = metadata.virtual_receive
                sample_list.append(df)
            elif metadata.sample_size == 0:
                # Zero-length payload; nothing to consume for this record
                continue
            else:
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
    def time_variable(self) -> Literal['virtual_send', 'virtual_receive']:
        return self._time_variable

    @time_variable.setter
    def time_variable(self, var: Literal['virtual_send', 'virtual_receive']) -> None:
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
    def use_send_time(self) -> bool:
        return self._use_send_time

    @use_send_time.setter
    def use_send_time(self, flag: bool) -> None:
        self._use_send_time = flag
        self.time_variable = 'virtual_send' if flag else 'virtual_receive'
        self.reset_time_range()
