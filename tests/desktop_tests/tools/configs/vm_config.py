# -*- coding: utf-8 -*-
import json
from rich import print
from os import getcwd
from os.path import join
from pydantic import BaseModel, conint
from host_tools import singleton


class SystemConfigModel(BaseModel):
    """
    A Pydantic model for validating the system configuration parameters.

    Attributes:
        cpus (int): The number of CPUs allocated for the system. Must be an integer >= 1.
        memory (int): The amount of memory in MB. Must be an integer >= 512.
    """

    cpus: conint(ge=1)
    memory: conint(ge=512)
    audio: bool
    nested_virtualization: bool
    speculative_execution_control: bool


@singleton
class VmConfig:
    """
    Configuration class for system settings.

    Attributes:
        cpus (int): The number of CPUs allocated for the system.
        memory (int): The amount of memory in MB.
    """
    def __init__(self, config_path: str = join(getcwd(), 'vm_config.json')):
        self.config_path = config_path
        self._config = self._load_config(self.config_path)
        self.cpus = self._config.cpus
        self.memory = self._config.memory
        self.audio = self._config.audio
        self.nested_virtualization = self._config.nested_virtualization
        self.speculative_execution_control = self._config.speculative_execution_control

    @staticmethod
    def _load_config(file_path: str) -> SystemConfigModel:
        """
        Loads the system configuration from a JSON file and returns a SystemConfigModel instance.

        :param file_path: The path to the configuration JSON file.
        :return: An instance of SystemConfigModel containing the loaded configuration.
        """
        with open(file_path, 'r') as f:
            return SystemConfigModel(**json.load(f))

    def display_config(self):
        """
        Displays the loaded system configuration.
        """
        print(
            f"[green]|INFO| System Configuration:\n"
            f"  CPUs: {self.cpus}\n"
            f"  Memory: {self.memory}MB\n"
            f"  Audio Enabled: {self.audio}\n"
            f"  Nested Virtualization: {self.nested_virtualization}\n"
            f"  Speculative Execution Control: {self.speculative_execution_control}"
        )
