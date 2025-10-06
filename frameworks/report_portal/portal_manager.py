# -*- coding: utf-8 -*-
import time
from typing import Optional

from report_portal import ReportPortal

class PortalManager:
    """
    Manager for Report Portal operations including launches, suites, and test results.

    Provides high-level interface for managing Report Portal launches,
    creating test suites, and sending test results with proper caching.
    """
    _suite_cache = {}

    def __init__(self,
            project_name: str,
            launch_name: str,
            launch_attributes: list[dict] = None,
            last_launch_connect: bool = True
        ):
        """
        Initialize PortalManager with project and launch configuration.

        :param project_name: Name of the Report Portal project
        :param launch_name: Name of the test launch
        :param launch_attributes: Optional attributes for the launch
        :param last_launch_connect: Whether to connect to the last launch
        """
        self.last_launch_connect = last_launch_connect
        self.launch_name = launch_name
        self.launch_attributes = launch_attributes
        self.rp = ReportPortal(project_name=project_name)
        self.__suites = None
        self.__suite_names = None
        self.__steps_items = None

    @property
    def suites(self) -> list:
        """
        Get list of test suites from the current launch.

        :return: List of suite items from Report Portal
        """
        if self.__suites is None:
            self.__suites = self.rp.get_suite().get_items_by_type()
        return self.__suites

    @property
    def suite_names(self) -> list:
        """
        Get list of suite names from the current launch.

        :return: List of suite names
        """
        if self.__suites is None:
            self.__suite_names = [suite.get("name") for suite in self.suites]
        return self.__suite_names

    @property
    def steps_items(self) -> list:
        """
        Get list of step items from the current launch.

        :return: List of step items from Report Portal
        """
        if self.__steps_items is None:
            self.__steps_items = self.rp.get_step().get_items_by_type()
        return self.__steps_items

    def __enter__(self):
        """
        Context manager entry point.

        :return: Self instance for context management
        """
        self.start_launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit point.

        :param exc_type: Exception type if any
        :param exc_val: Exception value if any
        :param exc_tb: Exception traceback if any
        """
        self.finish_launcher()

    def start_launch(self):
        """
        Start a new Report Portal launch.
        """
        self.rp.launch.start(name=self.launch_name, last_launch_connect=self.last_launch_connect, attributes=self.launch_attributes)

    def set_test_result(
            self,
            test_name: str,
            return_code: int,
            log_message: str = None,
            suite_uuid: str = None,
            status: str = None
    ):
        """
        Set test result in Report Portal with logs and status.

        :param test_name: Name of the test
        :param return_code: Test execution return code
        :param log_message: Optional log message for the test
        :param suite_uuid: UUID of the parent suite
        :param status: Optional status override
        """
        step = self.rp.get_step()
        suite_id = self.rp.launch.rp_client.get_id(item_type='suite', uuid=suite_uuid, cache=True)
        exist_step = self.get_exist_item(self.steps_items, test_name, suite_id)

        step_uuid = step.start(
            name=test_name,
            parent_item_id=suite_uuid,
            retry=True if exist_step else False,
            uuid=exist_step["uuid"] if exist_step else None
        )

        step.send_log(
            message=f"Test {test_name} started at {time.strftime('%Y-%m-%d %H:%M:%S')}",
            level="INFO",
            item_uuid=step_uuid
        )

        if log_message and str(log_message).lower() != 'nan':
            step.send_log(
                message=log_message,
                level="ERROR" if return_code != 0 else "WARN",
                item_uuid=step_uuid,
                print_output=False
            )

        step.finish(return_code=return_code, status=status)

    def create_suite(self, suite_name: str, parent_suite_uuid: Optional[str] = None):
        """
        Create or get existing test suite with caching.

        :param suite_name: Name of the suite to create
        :param parent_suite_uuid: Optional UUID of parent suite
        :return: Suite UUID
        """
        cache_key = f"{suite_name}_{parent_suite_uuid or self.rp.launch.uuid}"

        if cache_key not in self._suite_cache:
            suite = self.rp.get_suite()
            parent_id = suite.get_id(parent_suite_uuid) if parent_suite_uuid else None
            exists_suite = self.get_exist_item(self.suites, suite_name, parent_id)

            if exists_suite:
                self._suite_cache[cache_key] = exists_suite["uuid"]
            else:
                self._suite_cache[cache_key] = suite.create(
                    name=suite_name, parent_item_id=parent_suite_uuid
                )

        return self._suite_cache[cache_key]

    @staticmethod
    def get_exist_item(items: list, target_name: str, parent_id: Optional[str] = None) -> Optional[dict]:
        """
        Find existing item by name and parent ID.

        :param items: List of items to search in
        :param target_name: Name of the target item
        :param parent_id: Optional parent ID to match
        :return: Matching item dictionary or None
        """
        matching_item = next(
            (item for item in items if item.get('name') == target_name and item.get('parent') == parent_id),
            None
        )
        return matching_item

    def finish_launcher(self):
        """
        Finish and close the Report Portal launch.
        """
        self.rp.launch.finish()
