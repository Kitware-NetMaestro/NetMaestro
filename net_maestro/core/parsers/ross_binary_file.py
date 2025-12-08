from collections import namedtuple
import struct
from typing import BinaryIO, Literal, Optional

import pandas as pd


class ROSSFile:
    def __init__(self, filename: str) -> None:
        self.f: BinaryIO = open(filename, 'rb')
        self.content: bytes = self.f.read()

        self.engine_md_format: str = '@2i2d'
        self.engine_md_size: int = struct.calcsize(self.engine_md_format)

        self.engine_pe_format: str = '@13I13f'
        self.engine_pe_size: int = struct.calcsize(self.engine_pe_format)

        self.engine_kp_format: str = '@9I2f'
        self.engine_kp_size: int = struct.calcsize(self.engine_kp_format)

        self.engine_lp_format: str = '@8If'
        self.engine_lp_size: int = struct.calcsize(self.engine_lp_format)

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
        while True:
            md_bytes = self.content[byte_pos : byte_pos + self.engine_md_size]
            byte_pos += len(md_bytes)
            if not md_bytes:
                break
            md_record = namedtuple('md_record', 'flag sample_size virtual_time real_time')
            md = md_record._make(struct.unpack(self.engine_md_format, md_bytes))

            if md.sample_size == self.engine_pe_size:
                pe_bytes = self.content[byte_pos : byte_pos + self.engine_pe_size]
                byte_pos += len(pe_bytes)
                pe_record = namedtuple(
                    'pe_record',
                    'PE_ID events_processed events_aborted events_rolled_back '
                    'total_rollbacks secondary_rollbacks fossil_collection_attempts '
                    'pq_queue_size network_sends network_reads number_gvt pe_event_ties '
                    'all_reduce efficiency network_read_time network_other_time gvt_time '
                    'fossil_collect_time event_abort_time event_process_time pq_time '
                    'rollback_time cancel_q_time avl_time buddy_time lz4_time',
                )
                pe_data = pe_record._make(struct.unpack(self.engine_pe_format, pe_bytes))
                df = pd.DataFrame([pe_data])
                df['virtual_time'] = md.virtual_time
                df['real_time'] = md.real_time
                pe_list.append(df)
            elif md.sample_size == self.engine_kp_size:
                kp_bytes = self.content[byte_pos : byte_pos + self.engine_kp_size]
                byte_pos += len(kp_bytes)
                kp_record = namedtuple(
                    'kp_record',
                    'PE_ID KP_ID events_processed events_abort events_rolled_back '
                    'total_rollbacks secondary_rollbacks network_sends network_reads '
                    'time_ahead_gvt efficiency',
                )
                kp_data = kp_record._make(struct.unpack(self.engine_kp_format, kp_bytes))
                df = pd.DataFrame([kp_data])
                df['virtual_time'] = md.virtual_time
                df['real_time'] = md.real_time
                kp_list.append(df)
            elif md.sample_size == self.engine_lp_size:
                lp_bytes = self.content[byte_pos : byte_pos + self.engine_lp_size]
                byte_pos += len(lp_bytes)
                lp_record = namedtuple(
                    'lp_record',
                    'PE_ID KP_ID LP_ID events_processed events_abort events_rolled_back '
                    'network_sends network_reads efficiency',
                )
                lp_data = lp_record._make(struct.unpack(self.engine_lp_format, lp_bytes))
                df = pd.DataFrame([lp_data])
                df['virtual_time'] = md.virtual_time
                df['real_time'] = md.real_time
                lp_list.append(df)
            else:
                print('ERROR: found incorrect struct size')
                return

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
