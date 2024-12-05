# -*- coding: utf-8 -*-
from posixpath import join

class LinuxRemotePaths:
    def __init__(self, user_name: str):
        self.user_name = user_name
        self.home_dir = join("/home", user_name)
        self.script_path = join(self.home_dir, 'script.sh')
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
