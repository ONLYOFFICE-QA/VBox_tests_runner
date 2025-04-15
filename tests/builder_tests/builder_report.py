# -*- coding: utf-8 -*-
from os.path import dirname, isfile

from host_tools.utils import Dir

from frameworks import Report


class BuilderReport:

    def __init__(self, report_path: str):
        self.path = report_path
        self.dir = dirname(self.path)
        self.report = Report()
        Dir.create(self.dir, stdout=False)

    def column_is_empty(self, column_name: str) -> bool:
        if not self.report.read(self.path)[column_name].count() or not isfile(self.path):
            return True
        return False

    def _writer(self, mode: str, message: list, delimiter='\t', encoding='utf-8'):
        self.report.write(self.path, mode, message, delimiter, encoding)

    def exists(self) -> bool:
        return isfile(self.path)
