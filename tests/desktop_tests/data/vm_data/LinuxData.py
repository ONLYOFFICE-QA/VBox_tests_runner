# -*- coding: utf-8 -*-
from dataclasses import dataclass
from os.path import basename, splitext
from posixpath import join

from .vm_data import VmData


@dataclass
class LinuxData(VmData):
    def __post_init__(self):
        if not self.user or not self.version or not self.name or not self.ip:
            raise ValueError("User, version, name, ip is a required parameter.")
        self.home_dir = join('/home', self.user)
        self.script_path = join(self.home_dir, 'script.sh')
        self.script_dir = join(self.home_dir, 'scripts')
        self.desktop_testing_path = join(self.script_dir, splitext(basename(self.desktop_testing_url))[0])
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

    @property
    def start_service_commands(self) -> list:
        return [
            f'chmod +x {self.script_path}',
            'sudo systemctl daemon-reload',
            f'sudo systemctl start {self.my_service_name}'
        ]

    def my_service(self):
        return f'''\
        [Unit]
        Description=CustomBashScript

        [Service]
        Type=simple
        ExecStart=/bin/bash {self.script_path}
        User={self.user}

        [Install]
        WantedBy=multi-user.target\
        '''

    def script_sh(self) -> str:
        return f'''\
        #!/bin/bash
        cd {self.script_dir}
        git clone {'-b ' if self.branch else ''}{self.branch if self.branch else ''} {self.desktop_testing_url}
        cd {self.desktop_testing_path}
        python3 -m venv venv
        source ./venv/bin/activate
        python3 ./install_requirements.py
        invoke open-test -d -v {self.version}\
{' -u ' + self.old_version if self.old_version else ''}\
{' -t' if self.telegram else ''}\
{(' -c ' + self.custom_config_path) if self.custom_config else ''}\
{(' -l ' + self.lic_file) if self.custom_config else ''}\
        '''
