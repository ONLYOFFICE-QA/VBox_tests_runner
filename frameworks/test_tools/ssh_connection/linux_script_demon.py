# -*- coding: utf-8 -*-
from os.path import exists
from posixpath import join
from tempfile import gettempdir

class LinuxScriptDemon:
    """
    A class to manage and generate systemd service scripts for running custom bash scripts as services on a Linux system.
    """

    services_dir = join('/etc', 'systemd', 'system')

    def __init__(self, exec_script_path: str, user: str, name: str = 'my_script.service'):
        """
        Initialize the LinuxScriptDemon with the path to the bash script, user, and service name.
        :param exec_script_path: The path to the bash script to be executed by the service.
        :param user: The user under which the service will run.
        :param name: The name of the systemd service file. Defaults to 'my_script.service'.
        """
        self.exec_script_path = exec_script_path
        self.name = name
        self.user = user

    def generate(self) -> str:
        """
        Generate the content of the systemd service file.

        :return: A string representing the content of the systemd service file.
        """
        return f'''\
    [Unit]
    Description=CustomBashScript

    [Service]
    Type=simple
    ExecStart=/bin/bash {self.exec_script_path}
    User={self.user}
    Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/home/{self.user}/.local/bin"
    Environment="HOME=/home/{self.user}"
    Environment="SHELL=/bin/bash"
    Environment="ZDOTDIR=/tmp"
    Environment="BASH_ENV="

    [Install]
    WantedBy=multi-user.target\
    '''.strip()

    def start_demon_commands(self) -> list:
        """
        Generate the list of commands to start the service.

        :return: A list of shell commands to start the service.
        """
        return [
            f'chmod +x {self.exec_script_path}',
            'sudo systemctl daemon-reload',
            f'sudo systemctl start {self.name}'
        ]

    def change_service_dir_access_cmd(self) -> list:
        """
        Generate the list of commands to change access permissions of the service directory.

        :return: A list of shell commands to change the service directory permissions.
        """
        return [
            f'sudo chown {self.user}:{self.user} {self.services_dir}',
            f'sudo chmod u+w {self.services_dir}'
        ]

    def create(self, save_path: str = None) -> str:
        """
        Create the systemd service file at the specified path or in a temporary directory.
        :param save_path: The path to save the generated service file. If None, a temporary file is created.
        :return: The path to the created service file.
        """
        _path = save_path or self.services_dir if exists(self.services_dir) else join(gettempdir(), self.name)
        with open(_path, mode='w', newline='') as file:
            file.write('\n'.join(line.strip() for line in self.generate().split('\n')))
        return _path
