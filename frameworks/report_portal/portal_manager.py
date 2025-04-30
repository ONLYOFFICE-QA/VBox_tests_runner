# -*- coding: utf-8 -*-
import time
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
        self.__steps_items = None

    @property
    def suites(self) -> list:
        if self.__suites is None:
            self.__suites = self.rp.request.suite.get_suites(launch_id=self.rp.launch.id)
        return self.__suites

    @property
    def suite_names(self) -> list:
        if self.__suites is None:
            self.__suite_names = [suite.get("name") for suite in self.suites]
        return self.__suite_names

    @property
    def steps_items(self) -> list:
        if self.__steps_items is None:
            self.__steps_items = self.rp.request.step.get_steps(launch_id=self.rp.launch.id)
        return self.__steps_items

    @property
    def tests_items(self) -> list:
        if self.__tests_items is None:
            self.__tests_items = self.rp.request.test.get_tests(launch_id=self.rp.launch.id)
        return self.__tests_items

    def __enter__(self):
        self.start_launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finish_launcher()

    def start_launch(self):
        self.rp.launch.start(name=self.launch_name, last_launch_connect=True)

    def set_test_result(self, test_name: str, return_code: int, log_message: str = None, suite_uuid: str = None):
        step = self.rp.get_launch_step()
        suite_id = step.request.get_id(uuid=suite_uuid, cache=True)
        exist_step = self.get_exist_item(self.steps_items, test_name, suite_id)

        step_uuid = step.start(
            name=test_name,
            parent_item_id=suite_uuid,
            retry=True if exist_step else False,
            uuid=exist_step["uuid"] if exist_step else None
        )

        if log_message:
            step.send_log(message=log_message, level="ERROR" if return_code != 0 else "WARN", item_uuid=step_uuid)

        step.finish(return_code=return_code)

    def create_suite(self, suite_name: str, parent_suite_id: Optional[str] = None):
        cache_key = f"{suite_name}_{parent_suite_id}"

        if cache_key not in self._suite_cache:
            suite = self.rp.get_launch_suite()
            parent_id = suite.request.get_id(parent_suite_id) if parent_suite_id else None
            exists_suite = self.get_exist_item(self.suites, suite_name, parent_id)

            if exists_suite:
                self._suite_cache[cache_key] = exists_suite["uuid"]
            else:
                self._suite_cache[cache_key] = suite.create(
                    name=suite_name, parent_item_id=parent_suite_id
                )

        return self._suite_cache[cache_key]

    @staticmethod
    def get_exist_item(items: list, target_name: str, parent_id: Optional[str] = None) -> Optional[dict]:
        matching_item = next(
            (item for item in items if item.get('name') == target_name and item.get('parent') == parent_id),
            None
        )
        return matching_item

    def finish_launcher(self):
        self.rp.launch.finish()
