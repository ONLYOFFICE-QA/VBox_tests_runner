# -*- coding: utf-8 -*-
from .report import TestsRunnerReport


class TestsRunner:

    def __init__(self, base_version: str):
        self.base_version = base_version
        self.report = TestsRunnerReport(path=f"{base_version}.csv")
        self.package_checker = PackageURLChecker()

    def run(self):
        pass
