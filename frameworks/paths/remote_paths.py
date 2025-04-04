# -*- coding: utf-8 -*-
from posixpath import join

class RemotePaths:

    def __init__(self, user_name: str, os_type: str):
        self.os_type = os_type.lower() if os_type else ''
        self.user_name = user_name
        self.run_script_name = self._get_run_script_name()

        self.path_module = self._windows_path if 'windows' in self.os_type else join

        self.home_dir = self._join_path("C:\\Users" if 'windows' in self.os_type else "/home", self.user_name)

        self.script_dir = self._join_path(self.home_dir, 'scripts')
        self.script_path = self._join_path(self.home_dir, self.run_script_name)

        self.tg_dir = self._join_path(self.home_dir, '.telegram')
        self.tg_token_file = self._join_path(self.tg_dir, 'token')
        self.tg_chat_id_file = self._join_path(self.tg_dir, 'chat')
        self.proxy_config_file = self._join_path(self.tg_dir, 'proxy.json')
        self.github_token_dir = self._join_path(self.home_dir, '.github')
        self.github_token_path = self._join_path(self.github_token_dir, 'token')

    def _get_run_script_name(self) -> str:
        if 'vista' in self.os_type:
            return 'script.bat'

        if 'windows' in self.os_type:
            return 'script.ps1'

        return 'script.sh'

    def _join_path(self, *parts) -> str:
        return str(self.path_module(*parts))

    @staticmethod
    def _windows_path(*parts) -> str:
        return "\\".join(parts)
