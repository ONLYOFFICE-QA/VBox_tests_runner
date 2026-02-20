# -*- coding: utf-8 -*-
from dataclasses import dataclass
from abc import ABC, abstractmethod
from os.path import isfile, join
from host_tools import File

from .paths import LocalPaths


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
    @abstractmethod
    def status_bar(self):
        return False

    @property
    @abstractmethod
    def vm_names(self) -> list: ...

    @property
    def update_interval(self) -> int:
        return 0.5

    @property
    def tg_token(self) -> str:
        return self._read_file(self.token_file).strip()

    @property
    def token_file(self) -> str:
        return self._get_file_path('token_file', 'token')

    @property
    def restore_snapshot(self) -> bool:
        return self.config.get('restore_snapshot', True)

    @property
    def snapshot_name(self) -> str:
        return self.config.get('snapshot_name', None)

    @property
    def configurate(self) -> bool:
        return self.config.get('configurate', True)

    @property
    def tg_chat_id(self) -> str:
        return self._read_file(self.chat_id_file).strip()

    @property
    def chat_id_file(self) -> str:
        return self._get_file_path('chat_id_file', 'chat')

    @property
    def tg_report_chat_id(self) -> str | None:
        """Returns additional report chat ID if configured, otherwise None."""
        if not self.config.get('report_chat_id_file', '').strip():
            return None
        return self._read_file(self.report_chat_id_file).strip()

    @property
    def report_chat_id_file(self) -> str | None:
        """Returns path to additional report chat ID file if configured."""
        filename = self.config.get('report_chat_id_file', '').strip()
        if not filename:
            return None
        file_path = join(self.local_paths.tg_dir, filename)
        if not isfile(file_path):
            print(
                f"[red]|WARNING| Report chat id file "
                f"from config file not exists: {file_path}"
            )
            return None
        return file_path

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
