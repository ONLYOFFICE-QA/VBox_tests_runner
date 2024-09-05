# -*- coding: utf-8 -*-
import os
from dataclasses import dataclass
from os.path import join

from host_tools import File


@dataclass
class VmData:
    telegram: bool
    user: str
    ip: str
    name: str
    version: str
    old_version: str
    custom_config: bool
    desktop_testing_url: str = File.read_json(join(os.getcwd(), 'config.json'))['desktop_script']
    branch: str = File.read_json(join(os.getcwd(), 'config.json')).get('branch')
