# -*- coding: utf-8 -*-
from os.path import dirname, isfile

from host_tools import File
from host_tools.utils import Dir

from frameworks import Report


class BuilderReport(Report):

    def __init__(self, report_path: str):
        super().__init__()
        self.path = report_path
        self.dir = dirname(self.path)
        Dir.create(self.dir, stdout=False)

    def get_full(self) -> str:
        File.delete(self.path, stdout=False) if isfile(self.path) else ...
        self.merge(
            File.get_paths(self.dir, extension='csv'),
            self.path
        )
        return self.path

    def column_is_empty(self, column_name: str) -> bool:
        if not self.read(self.path)[column_name].count() or not isfile(self.path):
            return True
        return False

    def writer(self, mode: str, message: list, delimiter='\t', encoding='utf-8'):
        self.write(self.path, mode, message, delimiter, encoding)

    def exists(self) -> bool:
        return isfile(self.path)
