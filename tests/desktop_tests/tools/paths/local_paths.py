# -*- coding: utf-8 -*-
from os import getcwd
from os.path import join, expanduser
from host_tools import singleton


@singleton
class LocalPaths:
    project_dir: str = getcwd()
    tg_dir: str = join(expanduser('~'), '.telegram')
    tmp_dir: str = join(project_dir, 'tmp')
    know_hosts: str = join(expanduser('~'), '.ssh', 'known_hosts')
    lic_file: str = join(project_dir, 'test_lic.lickey')
    proxy_config: str = join(expanduser('~'), '.telegram', 'proxy.json')
