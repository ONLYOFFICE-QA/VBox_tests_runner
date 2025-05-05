# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import List

from rich import print
from pydantic import BaseModel, conint, constr, field_validator
from host_tools import singleton
from vboxwrapper import VirtualMachine


class NetworkConfigModel(BaseModel):
    """
    A Pydantic model for validating the network configuration parameters.

    Attributes:
        adapter_name (str): The name of the network adapter.
        connect_type (str): The type of network connection (e.g., "bridged").
    """
    adapter_name: constr(strip_whitespace=True, min_length=0)
    connect_type: constr(strip_whitespace=True, min_length=1)

    @field_validator('connect_type')
    def validate_connect_type(cls, v):
        connection_types = ["bridged", "nat", "hostonly", "intnet"]
        if v not in connection_types:
            raise ValueError(f'connect_type must be one of {", ".join(connection_types)}')
        return v


class SystemConfigModel(BaseModel):
    """
    A Pydantic model for validating the system configuration parameters.

    Attributes:
        cpus (int): The number of CPUs allocated for the system. Must be an integer >= 1.
        memory (int): The amount of memory in MB. Must be an integer >= 512.
        audio (bool): Whether audio is enabled.
        nested_virtualization (bool): Whether nested virtualization is enabled.
        speculative_execution_control (bool): Whether speculative execution control is enabled.
        network (NetworkConfigModel): Network configuration.
    """
    cpus: conint(ge=1)
    memory: conint(ge=512)
    audio: bool
    nested_virtualization: bool
    speculative_execution_control: bool
    network: NetworkConfigModel


@singleton
class VmConfig:
    vm_config_path = str(Path(__file__).resolve().parents[3] / "vm_configs" / "vm_config.json")

    """
    Configuration class for system settings.

    Attributes:
        cpus (int): The number of CPUs allocated for the system.
        memory (int): The amount of memory in MB.
        audio (bool): Whether audio is enabled.
        nested_virtualization (bool): Whether nested virtualization is enabled.
        speculative_execution_control (bool): Whether speculative execution control is enabled.
        network (NetworkConfigModel): Network configuration.
    """
    def __init__(self, config_path: str = None):
        self.config_path = config_path or self.vm_config_path
        self._config = self._load_config(self.config_path)
        self.cpus = self._config.cpus
        self.memory = self._config.memory
        self.audio = self._config.audio
        self.nested_virtualization = self._config.nested_virtualization
        self.speculative_execution_control = self._config.speculative_execution_control
        self.network = self._config.network
        self.host_adapters = self._get_valid_host_adapters_names()

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
            f"  Network Adapter: {self.network.adapter_name}\n"
            f"  Network Connection Type: {self.network.connect_type}"
        )

    @staticmethod
    def _get_valid_host_adapters_names() -> List[str]:
        adapters = VirtualMachine("").network.get_bridged_interfaces()
        return [
            adapter.get('Name') for adapter in adapters
            if adapter.get('Wireless') == 'No' and adapter.get('Status') == 'Up'
        ]

    def update_config(self, **kwargs):
        """
        Updates the configuration with new values and saves it to the file.

        :param kwargs: Key-value pairs to update in the configuration.
        """
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
            else:
                raise AttributeError(f"Invalid configuration key: {key}")

        # Save the updated configuration back to the file
        with open(self.config_path, 'w') as file:
            json.dump(self._config.model_dump(), file, indent=4)
