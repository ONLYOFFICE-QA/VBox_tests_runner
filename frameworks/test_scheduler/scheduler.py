# -*- coding: utf-8 -*-
"""
Test Scheduler Module

Provides automated VirtualBox test execution with intelligent version tracking
and scheduled execution capabilities.
"""

from os.path import isfile, getsize, getmtime
from typing import Dict, List, Optional
from datetime import datetime
import subprocess
from host_tools import File
import time
from rich import print
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from frameworks.package_checker import PackageURLChecker
from .config import SchedulerConfig


class TestScheduler:
    """
    Test scheduler for automated VirtualBox test execution.

    Provides functionality to schedule and run tests automatically
    when new versions are detected, with intelligent version tracking
    to avoid duplicate test execution.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        tested_versions_file: Optional[str] = None,
    ):
        """
        Initialize the test scheduler.

        :param config_path: Path to the configuration file
        :param tested_versions_file: Path to the file storing tested versions
        """
        self.config = SchedulerConfig(config_path)
        self.checker = PackageURLChecker()
        self.tested_versions_file = tested_versions_file or self.config.tested_versions_file
        self.scheduler = None

    def load_tested_versions(self) -> Dict[str, List[str]]:
        """
        Load previously tested versions from cache file.

        :return: Dictionary with builder and desktop tested versions
        """
        if isfile(self.tested_versions_file):
            return File.read_json(self.tested_versions_file)
        return {"builder": [], "desktop": []}

    def save_tested_versions(self, tested_versions: Dict[str, List[str]]) -> None:
        """
        Save tested versions to cache file.

        :param tested_versions: Dictionary with tested versions to save
        """
        File.write_json(self.tested_versions_file, tested_versions, indent=2)

    def check_and_run_tests(
        self,
        base_version: Optional[str] = None,
        max_builds: Optional[int] = None
    ):
        """
        Check for new versions and run tests if available.

        :param base_version: Base version to check for updates (uses config if None)
        :param max_builds: Maximum number of builds to check (uses config if None)
        """
        base_version = base_version or self.config.versions.base_version
        max_builds = max_builds or self.config.versions.max_builds

        if not base_version:
            print("[red]|ERROR| Base version not configured[/]")
            return

        print(f"[green]|INFO| Starting version check at {datetime.now()}[/]")
        self.checker.check_versions(
            base_version=base_version,
            max_builds=max_builds,
            stdout=True
        )

        new_versions = self._get_new_versions_to_test(base_version)
        print(f"[green]|INFO| New versions to test: {new_versions}[/]")
        if not new_versions:
            print("[blue]|INFO| No new versions to test[/]")
            return

        successful_tests = self._run_tests_for_versions(new_versions)
        if successful_tests:
            print(
                f"[green]|INFO| Completed {len(successful_tests)} test(s) successfully[/]"
            )

    def run_test(self, test_type: str, version: str) -> bool:
        """
        Execute a test of specified type for given version.

        :param test_type: Type of test (builder, desktop, etc.)
        :param version: Version to test
        :return: True if test executed successfully
        """
        command_attr = f"{test_type}_run_cmd"
        if not hasattr(self.config.commands, command_attr):
            print(f"[red]|ERROR| Unknown test type: {test_type}[/]")
            return False

        cmd_template = getattr(self.config.commands, command_attr)
        cmd = cmd_template.format(version=version)

        print(f"[green]|INFO| Running {test_type} test for version {version}[/]")
        print(f"[green]|INFO| Command: {cmd}[/]")

        result = subprocess.run(cmd, shell=True)
        return result.returncode == 0


    def start_scheduled_tests(
        self,
        start_hour: Optional[int] = None,
        end_hour: Optional[int] = None,
        interval_minutes: Optional[int] = None,
        base_version: Optional[str] = None,
        max_builds: Optional[int] = None,
    ):
        """
        Start scheduled test execution with specified parameters.

        :param start_hour: Hour to start checking (0-23, uses config if None)
        :param end_hour: Hour to stop checking (0-23, uses config if None)
        :param interval_minutes: Check interval in minutes (uses config if None)
        :param base_version: Base version to check for updates (uses config if None)
        :param max_builds: Maximum number of builds to check (uses config if None)
        """
        # Use config values as defaults
        start_hour = start_hour or self.config.scheduling.start_hour
        end_hour = end_hour or self.config.scheduling.end_hour
        interval_minutes = interval_minutes or self.config.scheduling.interval_minutes
        base_version = base_version or self.config.versions.base_version
        max_builds = max_builds or self.config.versions.max_builds

        print("[green]|INFO| Starting scheduled test runner[/]")
        print(
            f"[green]|INFO| Schedule: Every {interval_minutes} minutes from {start_hour}:00 to {end_hour}:00[/]"
        )

        try:
            self._initialize_scheduler(
                start_hour=start_hour,
                end_hour=end_hour,
                interval_minutes=interval_minutes,
                base_version=base_version,
                max_builds=max_builds,
            )
            self._run_scheduler()
        except Exception as e:
            print(f"[red]|ERROR| Failed to start scheduled tests: {e}[/]")

    def get_tested_versions_status(self) -> str:
        """
        Generate formatted status report for tested versions.

        :return: Formatted status string
        """
        status_lines = []
        tested_versions = self.load_tested_versions()

        for test_type in self.config.test_execution_order:
            test_versions = tested_versions.get(test_type, [])
            status_lines.append(
                f"[blue]{test_type.capitalize()} tested versions ({len(test_versions)})[/]:"
            )

            if test_versions:
                for i, version in enumerate(test_versions, 1):
                    status_lines.append(f"  {i:2d}. {version}")
            else:
                status_lines.append("  No versions tested yet")

            if test_type != self.config.test_execution_order[-1]:
                status_lines.append("")

        status_lines.extend(self._get_cache_file_info())
        return "\n".join(status_lines)

    def clear_tested_versions(self) -> bool:
        """
        Clear the tested versions cache.

        :return: True if successful, False otherwise
        """
        try:
            empty_versions = {"builder": [], "desktop": []}
            self.save_tested_versions(empty_versions)
            print("[green]|INFO| Tested versions cache cleared successfully[/]")
            return True
        except Exception as e:
            print(f"[red]|ERROR| Failed to clear tested versions cache: {e}[/]")
            return False

    def display_config(self):
        """Display the current scheduler configuration."""
        self.config.display_config()

    def update_config(self, **kwargs) -> bool:
        """
        Update scheduler configuration.

        :param kwargs: Configuration parameters to update
        :return: True if successful, False otherwise
        """
        try:
            self.config.update_config(**kwargs)
            print("[green]|INFO| Configuration updated successfully[/]")
            return True
        except Exception as e:
            print(f"[red]|ERROR| Failed to update configuration: {e}[/]")
            return False

    def validate_config(self) -> bool:
        """
        Validate the current configuration.

        :return: True if configuration is valid, False otherwise
        """
        return self.config.validate_config()

    # Private methods

    def _get_new_versions_to_test(self, base_version: str) -> Dict[str, str]:
        """
        Identify new versions that need testing based on configured test execution order.

        :param base_version: Base version to check for updates
        :return: Dictionary mapping test types to their new versions
        """
        tested_versions = self.load_tested_versions()
        print(f"[green]|INFO| Tested versions: {tested_versions}[/]")
        report = self.checker.get_report(base_version=base_version)
        print(f"[green]|INFO| Report: {report}[/]")
        report.update_df()

        latest_versions = {
            "builder": report.get_last_exists_version(category="builder"),
            "desktop": report.get_last_exists_version(category="desktop"),
        }
        print(f"[green]|INFO| Latest versions: {latest_versions}[/]")

        new_versions = {}
        for test_type in self.config.test_execution_order:
            latest_version = latest_versions.get(test_type)
            if not latest_version:
                continue

            if latest_version not in tested_versions[test_type]:
                new_versions[test_type] = latest_version
                print(f"[green]|INFO| New {test_type} version found: {latest_version}[/]")
            else:
                print(f"[blue]|INFO| {test_type.capitalize()} version {latest_version} already tested[/]")

        return new_versions

    def _run_tests_for_versions(self, new_versions: Dict[str, str]) -> Dict[str, str]:
        """
        Execute tests for specified versions in configured order.

        :param new_versions: Dictionary with test types and versions to test
        :return: Dictionary with successfully tested versions
        """
        successful_tests = {}

        for test_type in self.config.test_execution_order:
            if test_type not in new_versions:
                print(f"[blue]|INFO| No new version for {test_type} test, skipping[/]")
                continue

            version = new_versions[test_type]
            success = self._execute_single_test(test_type, version)

            if success:
                successful_tests[test_type] = version
                self._update_tested_version_cache(test_type, version)

        return successful_tests

    def _execute_single_test(self, test_type: str, version: str) -> bool:
        """
        Execute a single test and handle its result.

        :param test_type: Type of test to execute
        :param version: Version to test
        :return: True if test completed successfully
        """
        try:
            if self.run_test(test_type, version):
                print(f"[green]|INFO| {test_type.capitalize()} test completed successfully[/]")
                return True
            else:
                print(f"[red]|ERROR| {test_type.capitalize()} test failed for version {version}[/]")
                return False
        except Exception as e:
            print(f"[red]|ERROR| {test_type.capitalize()} test error: {e}[/]")
            return False

    def _update_tested_version_cache(self, test_type: str, version: str) -> None:
        """
        Update the tested versions cache with a successful test result.

        :param test_type: Type of test that was completed
        :param version: Version that was successfully tested
        """
        tested_versions = self.load_tested_versions()
        tested_versions[test_type].append(version)

        # Keep only recent versions to prevent unlimited cache growth
        tested_versions[test_type] = tested_versions[test_type][-self.config.cache_max_versions :]

        self.save_tested_versions(tested_versions)
        print(f"[green]|INFO| Cache updated for {test_type} version {version}[/]")

    def _initialize_scheduler(
        self,
        start_hour: int,
        end_hour: int,
        interval_minutes: int,
        base_version: str,
        max_builds: int,
    ) -> None:
        """
        Initialize the background scheduler with specified parameters.

        :param start_hour: Hour to start checking
        :param end_hour: Hour to stop checking
        :param interval_minutes: Check interval in minutes
        :param base_version: Base version to check
        :param max_builds: Maximum builds to check
        """
        self.scheduler = BackgroundScheduler()
        cron_trigger = CronTrigger(minute=f"*/{interval_minutes}", hour=f"{start_hour}-{end_hour}")

        self.scheduler.add_job(
            func=lambda: self.check_and_run_tests(base_version, max_builds),
            trigger=cron_trigger,
            id="version_check_and_tests",
            replace_existing=True,
        )

    def _run_scheduler(self) -> None:
        """
        Start and run the scheduler until interrupted.
        """
        print("[green]|INFO| Scheduler configured. Starting background execution...[/]")
        print("[yellow]|INFO| Press Ctrl+C to stop the scheduler[/]")

        self.scheduler.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[yellow]|INFO| Stopping scheduler...[/]")
            self.scheduler.shutdown()

        print("[green]|INFO| Scheduler stopped successfully[/]")

    def _get_cache_file_info(self) -> List[str]:
        """
        Get cache file information for status report.

        :return: List of cache file status lines
        """
        info_lines = [f"\n[yellow]Tested versions cache file: {self.tested_versions_file}[/]"]

        if isfile(self.tested_versions_file):
            size = getsize(self.tested_versions_file)
            mtime = datetime.fromtimestamp(getmtime(self.tested_versions_file))
            info_lines.append(f"[yellow]Cache file size: {size} bytes, last modified: {mtime}[/]")
        else:
            info_lines.append("[yellow]Cache file does not exist[/]")

        return info_lines
