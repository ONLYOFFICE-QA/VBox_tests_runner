# -*- coding: utf-8 -*-
from posixpath import join

class RemotePaths:

    def __init__(self, user_name: str, os_info: dict):
        self.__home_dir = None
        self.os_type = os_info['type']
        self.os_name = os_info['name']
        self.user_name = user_name
        self.run_script_name = self._get_run_script_name()

        self.script_dir = self._join_path(self.home_dir, 'scripts')
        self.script_path = self._join_path(self.home_dir, self.run_script_name)

        self.tg_dir = self._join_path(self.home_dir, '.telegram')
        self.tg_token_file = self._join_path(self.tg_dir, 'token')
        self.tg_chat_id_file = self._join_path(self.tg_dir, 'chat')
        self.proxy_config_file = self._join_path(self.tg_dir, 'proxy.json')
        self.github_token_dir = self._join_path(self.home_dir, '.github')
        self.github_token_path = self._join_path(self.github_token_dir, 'token')

    @property
    def home_dir(self) -> str:
        if self.__home_dir is None:
            if 'windows' in self.os_type:
                self.__home_dir = self._join_path(self._join_path("C:", "Users"), self.user_name)
            else:
                self.__home_dir = self._join_path("/home", self.user_name)
        return self.__home_dir

    def _get_run_script_name(self) -> str:
        if 'windows' in self.os_type:
            return 'script.bat' if 'vista' in self.os_name else 'script.ps1'
        return 'script.sh'

    def _join_path(self, *parts) -> str:
        return str(join(*parts))
