# -*- coding: utf-8 -*-
from dataclasses import dataclass
from os.path import isfile, join
from typing import Dict, List

from host_tools import File, HostInfo

from frameworks.test_data import TestData
from tests.conversion_tests.conversion_paths import ConversionLocalPaths

@dataclass
class ConversionTestData(TestData):
    version: str
    config_path: str
    __status_bar: bool | None = None
    __config = None
    __restore_snapshot: bool = True
    __snapshot_name: str = None
    __configurate: bool = True
    __update_interval: int = 60


    def __post_init__(self):
        super().__post_init__()

    @property
    def status_bar(self) -> bool | None:
        return self.__status_bar

    @status_bar.setter
    def status_bar(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError("status_bar must be a boolean value")
        self.__status_bar = value

    @property
    def config(self) -> dict:
        if self.__config is None:
            self.__config = self._read_config()
        return self.__config

    @property
    def restore_snapshot(self) -> bool:
        return self.__restore_snapshot

    @property
    def snapshot_name(self) -> str:
        return self.__snapshot_name

    @property
    def configurate(self) -> bool:
        return self.__configurate

    @property
    def update_interval(self) -> int:
        return self.__update_interval

    @restore_snapshot.setter
    def restore_snapshot(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError("restore_snapshot must be a boolean value")
        self.__restore_snapshot = value

    @snapshot_name.setter
    def snapshot_name(self, value: str):
        if not isinstance(value, str):
            raise TypeError("snapshot_name must be a string value")
        self.__snapshot_name = value

    @configurate.setter
    def configurate(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError("configurate must be a boolean value")
        self.__configurate = value

    @property
    def vm_names(self) -> List[str]:
        return [name for name in self.config.get('hosts', []) if ('macos' in name.lower()) == HostInfo().is_mac]

    def _read_config(self) -> Dict:
        if not isfile(self.config_path):
            raise FileNotFoundError(f"[red]|ERROR| Configuration file not found: {self.config_path}")
        return File.read_json(self.config_path)
