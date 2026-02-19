from __future__ import annotations

import logging
import struct
from struct import Struct
from typing import BinaryIO, NamedTuple

import pandas as pd

from .schema import ENDIAN, infer_endian, validate_time_columns

logger = logging.getLogger(__name__)

# Metadata
META_FIELDS = (
    'source_lp',
    'dest_lp',
    'virtual_send',
    'virtual_receive',
    'real_times',
    'sample_size',
)
SAMPLE_SIZE_INDEX = META_FIELDS.index('sample_size')
META_FORMAT = f'{ENDIAN}IIfffI'
META_STRUCT = struct.Struct(META_FORMAT)


class META(NamedTuple):
    source_lp: int
    dest_lp: int
    virtual_send: float
    virtual_receive: float
    real_times: float
    sample_size: int


# SimpleP2P payload
SIMPLEP2P_FIELDS = ('event_type',)
SIMPLEP2P_FORMAT = f'{ENDIAN}i'
SIMPLEP2P_STRUCT = struct.Struct(SIMPLEP2P_FORMAT)


class SimpleP2P(NamedTuple):
    event_type: int


def _meta_format(endian: str) -> str:
    return f'{endian}IIfffI'


def _sp2p_format(endian: str) -> str:
    return f'{endian}i'


DEFAULT_TIME_KEY = 'virtual_send'
ALT_TIME_KEY = 'virtual_receive'
TIME_COLUMNS = [DEFAULT_TIME_KEY, ALT_TIME_KEY]


class EventFile:
    """Parser for event-trace binary files.

    Each record consists of a fixed-size metadata header followed by a payload.
    The header's sample_size selects the payload layout.
    """

    def __init__(self, filename: str) -> None:
        self.f: BinaryIO = open(filename, 'rb')
        self.content: bytes = self.f.read()

        # Detect endianness from first header
        known_payload_sizes = {struct.calcsize(_sp2p_format(e)) for e in ('<', '>')}
        detected_endian = infer_endian(
            _meta_format, SAMPLE_SIZE_INDEX, self.content, known_payload_sizes
        )

        self.metadata_struct: Struct = Struct(_meta_format(detected_endian))
        self.metadata_size: int = META_STRUCT.size

        # TODO: will need to figure out a way to not hardcode this
        self.simplep2p_struct: Struct = Struct(_sp2p_format(detected_endian))
        self.simplep2p_size: int = SIMPLEP2P_STRUCT.size

        self._use_send_time: bool = True
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

            if metadata.sample_size == self.simplep2p_size and (
                byte_pos + self.simplep2p_size <= len(self.content)
            ):
                sp_tuple = self.simplep2p_struct.unpack_from(self.content, byte_pos)
                byte_pos += self.simplep2p_size
                sp_data = SimpleP2P(*sp_tuple)
                df = pd.DataFrame([sp_data])
                df['source_lp'] = metadata.source_lp
                df['dest_lp'] = metadata.dest_lp
                df['virtual_send'] = metadata.virtual_send
                df['virtual_receive'] = metadata.virtual_receive
                sample_list.append(df)
            elif metadata.sample_size == 0:
                # Zero-length payload
                continue
            else:
                remaining = len(self.content) - byte_pos
                logger.warning(
                    'Stopping parse due to invalid payload size: size=%d, remaining=%d',
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
    def use_send_time(self) -> bool:
        return self._use_send_time

    @use_send_time.setter
    def use_send_time(self, flag: bool) -> None:
        self._use_send_time = flag
        self.time_variable = 'virtual_send' if flag else 'virtual_receive'
        self.reset_time_range()
