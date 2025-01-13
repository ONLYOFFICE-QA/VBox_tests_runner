# -*- coding: utf-8 -*-

class RemotePaths:

    def __init__(self, user_name: str, os_type: str):
        self.os_type = os_type.lower() if os_type else ''
        self.user_name = user_name
        self.run_script_name = self._get_run_script_name()

        if self.run_script_name.endswith(".bat"):
            from os.path import join
        else:
            from posixpath import join

        self.home_dir = join("C:\\Users" if 'windows' in self.os_type else "/home", self.user_name)
        self.script_path = join(self.home_dir, self.run_script_name)
        self.script_dir = join(self.home_dir, 'scripts')
        self.desktop_testing_path = join(self.script_dir, 'desktop_testing')
        self.report_dir = join(self.desktop_testing_path, 'reports')
        self.custom_config_path = join(self.script_dir, 'custom_config.json')
        self.tg_dir = join(self.home_dir, '.telegram')
        self.tg_token_file = join(self.tg_dir, 'token')
        self.tg_chat_id_file = join(self.tg_dir, 'chat')
        self.proxy_config_file = join(self.tg_dir, 'proxy.json')
        self.services_dir = join('/etc', 'systemd', 'system')
        self.my_service_name = 'myscript.service'
        self.my_service_path = join(self.services_dir, self.my_service_name)
        self.lic_file = join(self.script_dir, 'test_lic.lickey')

    def _get_run_script_name(self) -> str:
        if 'vista' in self.os_type:
            return 'script.bat'

        if 'windows' in self.os_type:
            return 'script.ps1'

        return 'script.sh'
