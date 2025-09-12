# -*- coding: utf-8 -*-
from rich import print
from tests.common import BaseTest
from frameworks.test_tools import TestToolsWindows, TestToolsLinux, TestTools
from .tools import DesktopTestData, DesktopTestTools


class DesktopTest(BaseTest):
    def __init__(self, vm_name: str, test_data: DesktopTestData):
        """
        Initialize DesktopTest instance
        :param vm_name: Name of the virtual machine
        :param test_data: Test data object
        """
        super().__init__(vm_name, test_data)
        self.test_tools_helper = DesktopTestTools(vm_name=vm_name, test_data=self.data)

    def run(self, headless: bool = False, max_attempts: int = 5, interval: int = 5) -> None:
        """
        Run desktop test with retry mechanism
        :param headless: Run in headless mode
        :param max_attempts: Maximum number of retry attempts
        :param interval: Delay between retries in seconds
        """
        if not self.test_tools_helper.is_incompatible_package():
            return

        if not self.test_tools_helper.check_package_exists():
            return

        self.run_with_retry(lambda h: self.test_tools_helper.run_test(h), headless, max_attempts, interval)

    def _get_test_tools(self) -> TestTools:
        """
        Get appropriate test tools for the OS
        :return: TestTools instance
        """
        if 'windows' in self.vm.os_type:
            return TestToolsWindows(vm=self.vm, test_data=self.data)
        return TestToolsLinux(vm=self.vm, test_data=self.data)

    def handle_failure(self) -> None:
        """Handle test failure"""
        self.test_tools_helper.handle_vm_creation_failure()
