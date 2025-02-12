# -*- coding: utf-8 -*-
from os import getcwd
from os.path import join, expanduser


class LocalPaths:
    project_dir: str = getcwd()
    home_dir = expanduser('~')
    tg_dir: str = join(home_dir, '.telegram')
    tmp_dir: str = join(project_dir, 'tmp')
    know_hosts: str = join(home_dir, '.ssh', 'known_hosts')
    lic_file: str = join(project_dir, 'test_lic.lickey')
    proxy_config: str = join(home_dir, '.telegram', 'proxy.json')
    github_token: str = join(home_dir, '.github', 'token')
