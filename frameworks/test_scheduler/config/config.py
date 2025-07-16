# -*- coding: utf-8 -*-
"""
Test Scheduler Configuration Module

Provides Pydantic-based configuration management for the Test Scheduler
with validation and type safety.
"""

import json
from pathlib import Path
from typing import Optional, List
import re
from rich import print
from pydantic import BaseModel, conint, constr, field_validator
from host_tools import singleton


class SchedulingConfigModel(BaseModel):
    """
    A Pydantic model for validating the scheduling configuration parameters.

    Attributes:
        start_hour (int): Hour to start checking (0-23).
        end_hour (int): Hour to stop checking (0-23).
        interval_minutes (int): Check interval in minutes (must be >= 1).
    """

    start_hour: conint(ge=0, le=23)
    end_hour: conint(ge=0, le=23)
    interval_minutes: conint(ge=1)

    @field_validator("end_hour")
    def validate_end_hour(cls, v, info):
        """
        Validate that end_hour is greater than start_hour.

        :param v: The end_hour value to validate
        :param info: ValidationInfo containing other field values
        """
        if "start_hour" in info.data and v <= info.data["start_hour"]:
            raise ValueError("end_hour must be greater than start_hour")
        return v


class CommandConfigModel(BaseModel):
    """
    A Pydantic model for validating the command configuration parameters.

    Attributes:
        builder_run_cmd (str): Command template for running builder tests.
        desktop_run_cmd (str): Command template for running desktop tests.
    """

    builder_run_cmd: constr(strip_whitespace=True, min_length=1)
    desktop_run_cmd: constr(strip_whitespace=True, min_length=1)

    @field_validator("builder_run_cmd", "desktop_run_cmd")
    def validate_commands_have_version_placeholder(cls, v):
        """
        Validate that command templates contain {version} placeholder.

        :param v: The command string to validate
        """
        if "{version}" not in v:
            raise ValueError("Command must contain {version} placeholder")
        return v


class VersionConfigModel(BaseModel):
    """
    A Pydantic model for validating the version configuration parameters.

    Attributes:
        base_version (str): Base version to check for updates.
        max_builds (int): Maximum number of builds to check (must be >= 1).
    """

    base_version: constr(strip_whitespace=True, min_length=1)
    max_builds: conint(ge=1)

    @field_validator("base_version")
    def validate_base_version_format(cls, v):
        """
        Validate base version format (x.y.z).

        :param v: The version string to validate
        """
        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError('base_version must be in format x.y.z (e.g., "9.0.4")')
        return v


class TestSchedulerConfigModel(BaseModel):
    """
    A Pydantic model for validating the complete test scheduler configuration.

    Attributes:
        scheduling (SchedulingConfigModel): Scheduling configuration.
        test_execution_order (List[str]): Order of test execution (also defines enabled tests).
        commands (CommandConfigModel): Command configuration.
        versions (VersionConfigModel): Version configuration.
        tested_versions_file (str): Path to the tested versions cache file.
        cache_max_versions (int): Maximum number of versions to keep in cache.
    """

    scheduling: SchedulingConfigModel
    test_execution_order: List[constr(strip_whitespace=True, min_length=1)]
    commands: CommandConfigModel
    versions: VersionConfigModel
    tested_versions_file: constr(strip_whitespace=True, min_length=1) = (
        "tested_versions.json"
    )
    cache_max_versions: conint(ge=1) = 10

    @field_validator("test_execution_order")
    def validate_test_execution_order(cls, v):
        """
        Validate that test execution order contains only valid test types.

        :param v: List of test execution order
        """
        valid_tests = {"builder", "desktop"}
        for test in v:
            if test not in valid_tests:
                raise ValueError(
                    f"Invalid test type '{test}'. Valid types: {valid_tests}"
                )

        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Test execution order contains duplicate entries")

        return v


@singleton
class SchedulerConfig:
    """
    Configuration class for Test Scheduler settings.

    Attributes:
        scheduling (SchedulingConfigModel): Scheduling configuration.
        test_execution_order (List[str]): Order of test execution (also defines enabled tests).
        commands (CommandConfigModel): Command configuration.
        versions (VersionConfigModel): Version configuration.
        tested_versions_file (str): Path to the tested versions cache file.
        cache_max_versions (int): Maximum number of versions to keep in cache.
    """

    scheduler_config_path = str(
        Path(__file__).resolve().parents[3] / "scheduler_config.json"
    )

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the scheduler configuration.

        :param config_path: Path to the configuration file
        """
        self.config_path = config_path or self.scheduler_config_path
        self._config = self._load_config(self.config_path)
        self.scheduling = self._config.scheduling
        self.test_execution_order = self._config.test_execution_order
        self.commands = self._config.commands
        self.versions = self._config.versions
        self.tested_versions_file = self._config.tested_versions_file
        self.cache_max_versions = self._config.cache_max_versions

    @staticmethod
    def _load_config(file_path: str) -> TestSchedulerConfigModel:
        """
        Loads the scheduler configuration from a JSON file and returns a TestSchedulerConfigModel instance.

        :param file_path: The path to the configuration JSON file.
        :return: An instance of TestSchedulerConfigModel containing the loaded configuration.
        """
        with open(file_path, "r") as f:
            config_data = json.load(f)

        # Transform flat structure to nested structure
        transformed_config = {
            "scheduling": {
                "start_hour": config_data.get("start_hour"),
                "end_hour": config_data.get("end_hour"),
                "interval_minutes": config_data.get("interval_minutes"),
            },
            "test_execution_order": config_data.get("test_execution_order", []),
            "commands": {
                "builder_run_cmd": config_data.get("builder_run_cmd"),
                "desktop_run_cmd": config_data.get("desktop_run_cmd"),
            },
            "versions": {
                "base_version": config_data.get("base_version"),
                "max_builds": config_data.get("max_builds"),
            },
            "tested_versions_file": config_data.get(
                "tested_versions_file", "tested_versions.json"
            ),
            "cache_max_versions": config_data.get("cache_max_versions", 10),
        }

        return TestSchedulerConfigModel(**transformed_config)

    def display_config(self):
        """
        Displays the loaded scheduler configuration.
        """
        print(
            f"[green]|INFO| Test Scheduler Configuration:[/]\n"
            f"  [blue]Scheduling:[/]\n"
            f"    Start Hour: {self.scheduling.start_hour}\n"
            f"    End Hour: {self.scheduling.end_hour}\n"
            f"    Interval (minutes): {self.scheduling.interval_minutes}\n"
            f"  [blue]Test Execution:[/]\n"
            f"    Execution Order: {' -> '.join(self.test_execution_order)}\n"
            f"  [blue]Commands:[/]\n"
            f"    Builder Command: {self.commands.builder_run_cmd}\n"
            f"    Desktop Command: {self.commands.desktop_run_cmd}\n"
            f"  [blue]Versions:[/]\n"
            f"    Base Version: {self.versions.base_version}\n"
            f"    Max Builds: {self.versions.max_builds}\n"
            f"  [blue]Cache:[/]\n"
            f"    Tested Versions File: {self.tested_versions_file}\n"
            f"    Max Cached Versions: {self.cache_max_versions}"
        )

    def update_config(self, **kwargs):
        """
        Updates the configuration with new values and saves it to the file.

        :param kwargs: Key-value pairs to update in the configuration.
        """
        # Create a copy of current config for updating
        config_dict = self._config.model_dump()

        # Update nested structure
        for key, value in kwargs.items():
            if "." in key:
                # Handle nested keys like 'scheduling.start_hour'
                section, field = key.split(".", 1)
                if section in config_dict:
                    config_dict[section][field] = value
                else:
                    raise AttributeError(f"Invalid configuration section: {section}")
            else:
                # Handle top-level keys
                if key in config_dict:
                    config_dict[key] = value
                else:
                    raise AttributeError(f"Invalid configuration key: {key}")

        # Validate updated configuration
        updated_config = TestSchedulerConfigModel(**config_dict)

        # Transform back to flat structure for saving
        flat_config = {
            "start_hour": updated_config.scheduling.start_hour,
            "end_hour": updated_config.scheduling.end_hour,
            "interval_minutes": updated_config.scheduling.interval_minutes,
            "test_execution_order": updated_config.test_execution_order,
            "builder_run_cmd": updated_config.commands.builder_run_cmd,
            "desktop_run_cmd": updated_config.commands.desktop_run_cmd,
            "base_version": updated_config.versions.base_version,
            "max_builds": updated_config.versions.max_builds,
            "tested_versions_file": updated_config.tested_versions_file,
            "cache_max_versions": updated_config.cache_max_versions,
        }

        # Save the updated configuration back to the file
        with open(self.config_path, "w") as file:
            json.dump(flat_config, file, indent=4)

        # Update internal state
        self._config = updated_config
        self.scheduling = self._config.scheduling
        self.test_execution_order = self._config.test_execution_order
        self.commands = self._config.commands
        self.versions = self._config.versions
        self.tested_versions_file = self._config.tested_versions_file
        self.cache_max_versions = self._config.cache_max_versions

    def get_config_dict(self) -> dict:
        """
        Get the configuration as a dictionary.

        :return: Configuration dictionary
        """
        return self._config.model_dump()

    def validate_config(self) -> bool:
        """
        Validate the current configuration.

        :return: True if configuration is valid, False otherwise
        """
        try:
            # Re-validate the current configuration
            TestSchedulerConfigModel(**self._config.model_dump())
            return True
        except Exception as e:
            print(f"[red]|ERROR| Configuration validation failed: {e}[/]")
            return False
