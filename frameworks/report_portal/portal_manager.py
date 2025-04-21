# -*- coding: utf-8 -*-
from typing import Optional

from report_portal import ReportPortal

class PortalManager:
    _suite_cache = {}

    def __init__(self, project_name: str, launch_name: str):
        self.launch_name = launch_name
        self.rp = ReportPortal(project_name=project_name)

    def __enter__(self):
        self.start_launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finish_launcher()

    def start_launch(self):
        self.rp.launch.start(name=self.launch_name)

    def start_test(self, test_name: str, suite_id: Optional[str] = None) -> ReportPortal.test:
        test = self.rp.test
        test.start(test_name=test_name, parent_item_id=suite_id)
        return test

    def create_suite(self, suite_name: str, parent_suite_id: Optional[str] = None):
        cache_key = f"{suite_name}_{parent_suite_id}"
        if cache_key in self._suite_cache:
            suite_id = self._suite_cache[cache_key]
        else:
            suite_id = self.rp.suite.create(suite_name=suite_name, parent_suite_id=parent_suite_id)
            self._suite_cache[cache_key] = suite_id

        return suite_id

    def finish_launcher(self):
        self.rp.launch.finish()
