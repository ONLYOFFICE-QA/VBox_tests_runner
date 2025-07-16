# -*- coding: utf-8 -*-
from os.path import isfile, getsize, getmtime
from typing import Dict, List
from datetime import datetime
import json
import subprocess
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
        self.tested_versions_file = (
            tested_versions_file or self.config.tested_versions_file
        )
        self.scheduler = None

    def load_tested_versions(self) -> Dict[str, List[str]]:
        """
        Load previously tested versions from cache file.

        :return: Dictionary with builder and desktop tested versions
        """
        try:
            if isfile(self.tested_versions_file):
                with open(self.tested_versions_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[yellow]|WARNING| Could not load tested versions: {e}[/]")

        return {"builder": [], "desktop": []}

    def save_tested_versions(self, tested_versions: Dict[str, List[str]]) -> None:
        """
        Save tested versions to cache file.

        :param tested_versions: Dictionary with tested versions to save
        """
        try:
            with open(self.tested_versions_file, "w") as f:
                json.dump(tested_versions, f, indent=2)
        except Exception as e:
            print(f"[yellow]|WARNING| Could not save tested versions: {e}[/]")

    def check_and_run_tests(self, base_version: str = None, max_builds: int = None):
        """
        Check for new versions and run tests if available.

        This method checks for new builder and desktop versions and runs
        and desktop tests if new versions are found.

        :param base_version: Base version to check for updates (uses config if None)
        :param max_builds: Maximum number of builds to check (uses config if None)
        """
        # Use config values if not provided
        base_version = base_version or self.config.versions.base_version
        max_builds = max_builds or self.config.versions.max_builds

        print(f"[green]|INFO| Starting version check at {datetime.now()}[/]")

        try:
            # Load tested versions cache
            tested_versions = self.load_tested_versions()

            # Create package checker
            checker = PackageURLChecker()

            # Get latest version for builder tests
            builder_last_version = checker.get_report(
                base_version=base_version
            ).get_last_exists_version(category="builder")
            desktop_last_version = checker.get_report(
                base_version=base_version
            ).get_last_exists_version(category="desktop")

            tests_run = False

            # Check and run builder tests for new version
            if (
                builder_last_version
                and builder_last_version not in tested_versions["builder"]
            ):
                print(
                    f"[green]|INFO| New builder version found: {builder_last_version}[/]"
                )
                success = self.run_builder_test(builder_last_version)
                if success:
                    tested_versions["builder"].append(builder_last_version)
                    # Keep only last N tested versions to avoid file growth
                    tested_versions["builder"] = tested_versions["builder"][
                        -self.config.cache_max_versions :
                    ]
                    tests_run = True
            elif builder_last_version:
                print(
                    f"[blue]|INFO| Builder version {builder_last_version} already tested[/]"
                )

            # Check and run desktop tests for new version
            if (
                desktop_last_version
                and desktop_last_version not in tested_versions["desktop"]
            ):
                print(
                    f"[green]|INFO| New desktop version found: {desktop_last_version}[/]"
                )
                success = self.run_desktop_test(desktop_last_version)
                if success:
                    tested_versions["desktop"].append(desktop_last_version)
                    # Keep only last N tested versions to avoid file growth
                    tested_versions["desktop"] = tested_versions["desktop"][
                        -self.config.cache_max_versions :
                    ]
                    tests_run = True
            elif desktop_last_version:
                print(
                    f"[blue]|INFO| Desktop version {desktop_last_version} already tested[/]"
                )

            # Save updated tested versions if any tests were run
            if tests_run:
                self.save_tested_versions(tested_versions)
                print(f"[green]|INFO| Tests completed and cache updated[/]")
            else:
                print(f"[blue]|INFO| No new versions to test[/]")

        except Exception as e:
            print(f"[red]|ERROR| Version check failed: {e}[/]")

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
        print(
            f"[green]|INFO| Schedule: Every {interval_minutes} minutes from {start_hour}:00 to {end_hour}:00[/]"
        )

        try:
            # Create BackgroundScheduler instance for APScheduler 3.x
            self.scheduler = BackgroundScheduler()

            # Create cron trigger for the specified time range
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
