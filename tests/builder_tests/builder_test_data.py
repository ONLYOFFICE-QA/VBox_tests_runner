# -*- coding: utf-8 -*-
from dataclasses import dataclass
from os.path import isfile
from typing import Dict, List

from host_tools import File

from frameworks.test_data import TestData


@dataclass
class BuilderTestData(TestData):
    version: str
    config_path: str
    status_bar: bool = True

    def __post_init__(self):
        super().__post_init__()
        self.__config = None
        self.dep_test_branch = self.config.get('branch')

    @property
    def config(self) -> dict:
        if self.__config is None:
            self.__config = self._read_config()

        return self.__config

    @property
    def vm_names(self) -> List[str]:
        return self.config.get('hosts', [])

    def _read_config(self) -> Dict:
        if not isfile(self.config_path):
            raise FileNotFoundError(f"[red]|ERROR| Configuration file not found: {self.config_path}")
        return File.read_json(self.config_path)
