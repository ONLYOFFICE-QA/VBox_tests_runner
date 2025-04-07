# -*- coding: utf-8 -*-
from dataclasses import dataclass

from abc import ABC, abstractmethod
from os.path import isfile, join


from host_tools import File


from frameworks.test_data.paths import LocalPaths


@dataclass
class TestData(ABC):

    def __post_init__(self):
        self.local_paths = LocalPaths()
        self.__config = None

    @property
    @abstractmethod
    def config(self):
        ...

    @property
    def tg_token(self) -> str:
        return self._read_file(self.token_file).strip()

    @property
    def token_file(self) -> str:
        return self._get_file_path('token_file', 'token')

    @property
    def tg_chat_id(self) -> str:
        return self._read_file(self.chat_id_file).strip()

    @property
    def chat_id_file(self) -> str:
        return self._get_file_path('chat_id_file', 'chat')

    @staticmethod
    def _read_file(file_path: str) -> str:
        if not isfile(file_path):
            raise FileNotFoundError(f"[red]|ERROR| File not found: {file_path}")
        return File.read(file_path)

    def _get_file_path(self, config_key: str, default_filename: str) -> str:
        filename = self.config.get(config_key, '').strip()
        if filename:
            file_path = join(self.local_paths.tg_dir, filename)
            if isfile(file_path):
                return file_path
            print(
                f"[red]|WARNING| {config_key.replace('_', ' ').capitalize()} "
                f"from config file not exists: {file_path}"
            )
        return join(self.local_paths.tg_dir, default_filename)

