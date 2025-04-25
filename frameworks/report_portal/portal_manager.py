# -*- coding: utf-8 -*-
from typing import Optional

from report_portal import ReportPortal

class PortalManager:
    _suite_cache = {}

    def __init__(self, project_name: str, launch_name: str):
        self.launch_name = launch_name
        self.rp = ReportPortal(project_name=project_name)
        self.__suites = None
        self.__suite_names = None
        self.__tests_items = None

    @property
    def suites(self) -> list:
        if self.__suites is None:
            self.__suites = self.rp.suite.get_suites()
        return self.__suites

    @property
    def suite_names(self) -> list:
        if self.__suites is None:
            self.__suite_names = [suite.get("name") for suite in self.suites]
        return self.__suite_names

    @property
    def tests_items(self) -> list:
        if self.__tests_items is None:
            self.__tests_items = self.rp.get_items(item_type='TEST')
        return self.__tests_items

    def __enter__(self):
        self.start_launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finish_launcher()

    def start_launch(self):
        self.rp.launch.start(name=self.launch_name, last_launch_connect=True)

    def set_test_result(self, test_name: str, return_code: int, log_message: str = None, suite_uuid: str = None):
        test = self.rp.create_test(test_name)
        test.start(suite_uuid=suite_uuid)

        if log_message:
            test.send_log(message=log_message, level="ERROR" if return_code != 0 else "WARN")

        test.finish(return_code=return_code)

    def create_suite(self, suite_name: str, parent_suite_id: Optional[str] = None):
        cache_key = f"{suite_name}_{parent_suite_id}"
        if cache_key not in self._suite_cache:
            if suite_name in self.suite_names:
                self._suite_cache[cache_key] = self.suites[self.suite_names.index(suite_name)]["uuid"]
            else:
                self._suite_cache[cache_key] = self.rp.suite.create(
                    suite_name=suite_name, parent_suite_id=parent_suite_id
                )

        return self._suite_cache[cache_key]

    def finish_launcher(self):
        self.rp.launch.finish()
