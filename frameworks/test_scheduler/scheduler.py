# -*- coding: utf-8 -*-
from os.path import isfile, getsize, getmtime
from typing import Dict, List
from datetime import datetime
import json
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

    def __init__(self, config_path: str = None, tested_versions_file: str = None):
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

    def check_and_run_tests(self, base_version: str = None, max_builds: int = None):
        """
        Check for new versions and run tests if available.

        This method checks for new builder and desktop versions and runs
        tests if new versions are found.

        :param base_version: Base version to check for updates (uses config if None)
        :param max_builds: Maximum number of builds to check (uses config if None)
        """
        base_version = base_version or self.config.versions.base_version
        max_builds = max_builds or self.config.versions.max_builds

        if not base_version:
            print(f"[red]|ERROR| Base version not configured[/]")
            return

        print(f"[green]|INFO| Starting version check at {datetime.now()}[/]")
        self.checker.check_versions(base_version=base_version, max_builds=max_builds, stdout=False)

        new_versions = self._get_new_versions_to_test(base_version)
        if not new_versions:
            print(f"[blue]|INFO| No new versions to test[/]")
            return

        successful_tests = self._run_tests_for_versions(new_versions)
        if successful_tests:
            print(f"[green]|INFO| Completed {len(successful_tests)} test(s) successfully[/]")

    def _get_new_versions_to_test(self, base_version: str) -> Dict[str, str]:
        """
        Get new versions that need to be tested.

        :param base_version: Base version to check for updates
        :return: Dictionary with test types and their new versions
        """
        tested_versions = self.load_tested_versions()

        report = self.checker.get_report(base_version=base_version)
        latest_versions = {
            "builder": report.get_last_exists_version(category="builder"),
            "desktop": report.get_last_exists_version(category="desktop"),
        }

        new_versions = {}
        for test_type, latest_version in latest_versions.items():
            if latest_version and latest_version not in tested_versions[test_type]:
                new_versions[test_type] = latest_version
                print(f"[green]|INFO| New {test_type} version found: {latest_version}[/]")
            elif latest_version:
                print(f"[blue]|INFO| {test_type.capitalize()} version {latest_version} already tested[/]")

        return new_versions

    def _run_tests_for_versions(self, new_versions: Dict[str, str]) -> Dict[str, str]:
        """
        Run tests for the specified versions.

        :param new_versions: Dictionary with test types and versions to test
        :return: Dictionary with successfully tested versions
        """
        successful_tests = {}

        for test_type, version in new_versions.items():
            print(f"[green]|INFO| Running {test_type} test for version {version}[/]")

            test_method = getattr(self, f"run_{test_type}_test", None)
            if not test_method:
                print(f"[red]|ERROR| Test method for {test_type} not found[/]")
                continue

            try:
                if test_method(version):
                    successful_tests[test_type] = version
                    print(
                        f"[green]|INFO| {test_type.capitalize()} test completed successfully[/]"
                    )
                    # Update cache immediately after each successful test
                    self._update_single_tested_version(test_type, version)
                    print(
                        f"[green]|INFO| Cache updated for {test_type} version {version}[/]"
                    )
                else:
                    print(
                        f"[red]|ERROR| {test_type.capitalize()} test failed for version {version}[/]"
                    )
            except Exception as e:
                print(f"[red]|ERROR| {test_type.capitalize()} test error: {e}[/]")

        return successful_tests

    def _update_single_tested_version(self, test_type: str, version: str) -> None:
        """
        Update the tested versions cache with a single successful test result.

        :param test_type: Type of test (builder or desktop)
        :param version: Version that was successfully tested
        """
        tested_versions = self.load_tested_versions()
        tested_versions[test_type].append(version)

        # Keep only last N tested versions to avoid unlimited growth
        tested_versions[test_type] = tested_versions[test_type][
            -self.config.cache_max_versions :
        ]

        self.save_tested_versions(tested_versions)

    def run_builder_test(self, version: str) -> bool:
        """
        Run builder test for specified version.

        :param version: Version to test
        :return: True if successful, False otherwise
        """
        cmd = self.config.commands.builder_run_cmd.format(version=version)
        print(f"[green]|INFO| Running builder test for version {version}[/]")
        print(f"[green]|INFO| Command: {cmd}[/]")
        result = subprocess.run(cmd, shell=True)
        return result.returncode == 0

    def run_desktop_test(self, version: str) -> bool:
        """
        Run desktop test for specified version.

        :param version: Version to test
        :return: True if successful, False otherwise
        """
        cmd = self.config.commands.desktop_run_cmd.format(version=version)
        print(f"[green]|INFO| Running desktop test for version {version}[/]")
        print(f"[green]|INFO| Command: {cmd}[/]")
        result = subprocess.run(cmd, shell=True)
        return result.returncode == 0

    def start_scheduled_tests(
        self,
        start_hour: int = None,
        end_hour: int = None,
        interval_minutes: int = None,
        base_version: str = None,
        max_builds: int = None,
    ):
        """
        Start scheduled test execution with the specified parameters.

        :param start_hour: Hour to start checking (0-23, uses config if None)
        :param end_hour: Hour to stop checking (0-23, uses config if None)
        :param interval_minutes: Check interval in minutes (uses config if None)
        :param base_version: Base version to check for updates (uses config if None)
        :param max_builds: Maximum number of builds to check (uses config if None)
        """
        # Use config values if not provided
        start_hour = (
            start_hour if start_hour is not None else self.config.scheduling.start_hour
        )
        end_hour = end_hour if end_hour is not None else self.config.scheduling.end_hour
        interval_minutes = (
            interval_minutes
            if interval_minutes is not None
            else self.config.scheduling.interval_minutes
        )
        base_version = base_version or self.config.versions.base_version
        max_builds = max_builds or self.config.versions.max_builds

        print(f"[green]|INFO| Starting scheduled test runner[/]")
        print(f"[green]|INFO| Schedule: Every {interval_minutes} minutes from {start_hour}:00 to {end_hour}:00[/]")

        try:
            self.scheduler = BackgroundScheduler()

            cron_trigger = CronTrigger(
                minute=f"*/{interval_minutes}", hour=f"{start_hour}-{end_hour}"
            )

            # Add the scheduled job
            self.scheduler.add_job(
                func=lambda: self.check_and_run_tests(base_version, max_builds),
                trigger=cron_trigger,
                id="version_check_and_tests",
                replace_existing=True,
            )

            print(
                f"[green]|INFO| Scheduler configured. Starting background execution...[/]"
            )
            print(f"[yellow]|INFO| Press Ctrl+C to stop the scheduler[/]")

            # Start scheduler
            self.scheduler.start()

            try:
                # Keep the scheduler running
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print(f"\n[yellow]|INFO| Stopping scheduler...[/]")
                self.scheduler.shutdown()

            print(f"[green]|INFO| Scheduler stopped successfully[/]")

        except Exception as e:
            print(f"[red]|ERROR| Failed to start scheduled tests: {e}[/]")

    def get_tested_versions_status(self) -> str:
        """
        Get status of tested versions.

        :return: Formatted status string
        """
        status_lines = []
        tested_versions = self.load_tested_versions()

        status_lines.append(
            f"[blue]Builder tested versions ({len(tested_versions['builder'])})[/]:"
        )
        if tested_versions["builder"]:
            for i, version in enumerate(tested_versions["builder"], 1):
                status_lines.append(f"  {i:2d}. {version}")
        else:
            status_lines.append("  No versions tested yet")

        status_lines.append(
            f"\n[blue]Desktop tested versions ({len(tested_versions['desktop'])})[/]:"
        )
        if tested_versions["desktop"]:
            for i, version in enumerate(tested_versions["desktop"], 1):
                status_lines.append(f"  {i:2d}. {version}")
        else:
            status_lines.append("  No versions tested yet")

        status_lines.append(
            f"\n[yellow]Tested versions cache file: {self.tested_versions_file}[/]"
        )
        if isfile(self.tested_versions_file):
            size = getsize(self.tested_versions_file)
            mtime = datetime.fromtimestamp(getmtime(self.tested_versions_file))
            status_lines.append(
                f"[yellow]Cache file size: {size} bytes, last modified: {mtime}[/]"
            )
        else:
            status_lines.append("[yellow]Cache file does not exist[/]")

        return "\n".join(status_lines)

    def clear_tested_versions(self) -> bool:
        """
        Clear tested versions cache.

        :return: True if successful, False otherwise
        """
        try:
            empty_versions = {"builder": [], "desktop": []}
            self.save_tested_versions(empty_versions)
            print(f"[green]|INFO| Tested versions cache cleared successfully[/]")
            return True
        except Exception as e:
            print(f"[red]|ERROR| Failed to clear tested versions cache: {e}[/]")
            return False

    def display_config(self):
        """
        Display the current scheduler configuration.
        """
        self.config.display_config()

    def update_config(self, **kwargs) -> bool:
        """
        Update scheduler configuration.

        :param kwargs: Configuration parameters to update
        :return: True if successful, False otherwise
        """
        try:
            self.config.update_config(**kwargs)
            print(f"[green]|INFO| Configuration updated successfully[/]")
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
