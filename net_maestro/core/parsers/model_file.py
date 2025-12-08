from collections import namedtuple
import struct
from typing import BinaryIO, Literal, Optional

import pandas as pd


# note this actually reads the analysis lps files, which i believe would include engine data as
# well, if collected
class ModelFile:
    def __init__(self, filename: str) -> None:
        self.f: BinaryIO = open(filename, 'rb')
        self.content: bytes = self.f.read()

        self.md_format: str = '@QLLddii'
        self.md_sz: int = struct.calcsize(self.md_format)

        # TODO: will need to figure out a way to not hardcode this
        self.simplep2p_format: str = '@Qlldlld'
        self.simplep2p_size: int = struct.calcsize(self.simplep2p_format)

        self._use_virtual_time: bool = True
        self._time_variable: Literal['virtual_time', 'real_time'] = 'virtual_time'

        self._simplep2p_df: Optional[pd.DataFrame] = None
        self._min_time: Optional[float] = None
        self._max_time: Optional[float] = None

    def read(self) -> None:
        sample_list: list[pd.DataFrame] = []

        byte_pos = 0
        while True:
            md_bytes = self.content[byte_pos : byte_pos + self.md_sz]
            byte_pos += len(md_bytes)
            if not md_bytes:
                break
            md_record = namedtuple(
                'md_record', 'lp_id kp_id pe_id virtual_time real_time sample_size flag'
            )
            md = md_record._make(struct.unpack(self.md_format, md_bytes))

            # flag == 3 is model data
            if md.flag == 3 and md.sample_size == self.simplep2p_size:
                sp_bytes = self.content[byte_pos : byte_pos + self.simplep2p_size]
                byte_pos += len(sp_bytes)
                sp_record = namedtuple(
                    'sp_record',
                    'component_id send_count send_bytes send_time '
                    'receive_count receive_bytes receive_time',
                )
                sp_data = sp_record._make(struct.unpack(self.simplep2p_format, sp_bytes))
                df = pd.DataFrame([sp_data])
                df['lp_id'] = md.lp_id
                df['virtual_time'] = md.virtual_time
                df['real_time'] = md.real_time
                sample_list.append(df)
            else:
                print(f'sample of size {md.sample_size} found')
                return

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
