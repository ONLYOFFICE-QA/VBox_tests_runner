# -*- coding: utf-8 -*-
from typing import Optional
from reportportal_client.helpers import timestamp

from report_portal import ReportPortalTest, ReportPortalLauncher

class PortalManager:
    _launch_cache = {}
    _suite_cache = {}

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.rp_launcher = ReportPortalLauncher(self.project_name)
        self.launch_id = None
        self.test = None

    def start_launcher(self, launch_name: str) -> str:
        if launch_name in self._launch_cache:
            self.launch_id = self._launch_cache[launch_name]
        else:
            self.launch_id = self.rp_launcher.start_launch(name=launch_name)
            self.test = ReportPortalTest(self.rp_launcher.get_client())
            self._launch_cache[launch_name] = self.launch_id

        return self.launch_id

    def start_test(self, test_name: str, suite_id: Optional[str] = None):
        self.test.start_test(test_name=test_name, item_type="TEST", parent_item_id=suite_id)

    def create_suite(self, suite_name: str, parent_suite_id: Optional[str] = None):
        cache_key = f"{suite_name}_{parent_suite_id}"
        if cache_key in self._suite_cache:
            suite_id = self._suite_cache[cache_key]
        else:
            suite_id = self.test.start_test(test_name=suite_name, item_type="SUITE", parent_item_id=parent_suite_id)
            self._suite_cache[cache_key] = suite_id
            self.test.client.finish_test_item(
                item_id=suite_id,
                end_time=timestamp(),
                status="PASSED"
            )

        return suite_id

    def send_test_log(self, message: str, level: str = 'INFO'):
        self.test.send_log(message=message, level=level)

    def finish_test(self, return_code: int, status="PASSED"):
        self.test.finish_test(
            return_code=return_code,
            status=status
        )

    def finish_launcher(self):
        self.rp_launcher.finish_launch()
