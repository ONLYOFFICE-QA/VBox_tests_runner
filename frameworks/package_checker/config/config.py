# -*- coding: utf-8 -*-

from dataclasses import dataclass
from os import getcwd
from os.path import join, dirname, realpath
from host_tools import File, Str


@dataclass
class Config:
    host: str = "https://s3.eu-west-1.amazonaws.com/repo-doc-onlyoffice-com"
    template_path = join(dirname(realpath(__file__)), "templates.json")
    report_dir: str = join(getcwd(), 'reports', 'report_checker')

    def __post_init__(self):
        self.templates = File.read_json(self.template_path)
        self.host = Str.delete_last_slash(self.host)
