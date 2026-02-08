# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import List

from rich import print
from pydantic import BaseModel, conint, constr, field_validator
from vboxwrapper import VirtualMachine
from frameworks.decorators import class_cache


class NetworkConfigModel(BaseModel):
    """
    A Pydantic model for validating the network configuration parameters.

    Attributes:
        adapter_number (int): The number of the network adapter (1-8).
        adapter_name (str): The name of the network adapter.
        connect_type (str): The type of network connection (e.g., "bridged").
    """
    adapter_number: conint(ge=1, le=8) = 1
    adapter_name: constr(strip_whitespace=True, min_length=0) = ""
    connect_type: constr(strip_whitespace=True, min_length=1)

    @field_validator('connect_type')
    def validate_connect_type(cls, v):
        connection_types = ["bridged", "nat", "hostonly", "intnet"]
        if v not in connection_types:
            raise ValueError(f'connect_type must be one of {", ".join(connection_types)}')
        return v


class PartialNetworkConfigModel(BaseModel):
    """
    A Pydantic model for partial network configuration with all optional fields.

    Attributes:
        adapter_number (int): The number of the network adapter (1-8).
        adapter_name (str): The name of the network adapter.
        connect_type (str): The type of network connection (e.g., "bridged").
    """
    adapter_number: conint(ge=1, le=8) = 1
    adapter_name: constr(strip_whitespace=True, min_length=0) | None = None
    connect_type: constr(strip_whitespace=True, min_length=1) | None = None

    @field_validator('connect_type')
    def validate_connect_type(cls, v):
        if v is not None:
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
        network (list[NetworkConfigModel]): List of network adapter configurations.
    """
    cpus: conint(ge=1)
    memory: conint(ge=512)
    audio: bool
    nested_virtualization: bool
    speculative_execution_control: bool
    network: List[NetworkConfigModel]


class VmSpecificConfigModel(BaseModel):
    """
    A Pydantic model for validating VM-specific configuration parameters.
    All fields are optional to allow partial overrides of default settings.

    Attributes:
        cpus (int): The number of CPUs allocated for the system. Must be an integer >= 1.
        memory (int): The amount of memory in MB. Must be an integer >= 512.
        audio (bool): Whether audio is enabled.
        nested_virtualization (bool): Whether nested virtualization is enabled.
        speculative_execution_control (bool): Whether speculative execution control is enabled.
        network (list[PartialNetworkConfigModel]): List of partial network adapter configurations.
    """
    cpus: conint(ge=1) | None = None
    memory: conint(ge=512) | None = None
    audio: bool | None = None
    nested_virtualization: bool | None = None
    speculative_execution_control: bool | None = None
    network: List[PartialNetworkConfigModel] | None = None


class ConfigFileModel(BaseModel):
    """
    A Pydantic model for the complete configuration file structure.

    Attributes:
        default (SystemConfigModel): Default configuration for all VMs.
        vm_specific (dict): VM-specific configurations keyed by VM name.
    """
    default: SystemConfigModel
    vm_specific: dict[str, VmSpecificConfigModel] = {}


@class_cache
class VmConfig:
    """
    Configuration class for system settings with support for VM-specific overrides.

    Attributes:
        cpus (int): The number of CPUs allocated for the system.
        memory (int): The amount of memory in MB.
        audio (bool): Whether audio is enabled.
        nested_virtualization (bool): Whether nested virtualization is enabled.
        speculative_execution_control (bool): Whether speculative execution control is enabled.
        network (NetworkConfigModel): Network configuration.
        vm_name (str): Name of the VM for specific configuration.
    """
    vm_config_path = str(Path(__file__).resolve().parents[3] / "vm_configs" / "vm_config.json")

    def __init__(self, vm_name: str = None, config_path: str = None):
        """
        Initialize VmConfig with optional VM-specific settings.

        :param vm_name: Name of the VM to load specific configuration for
        :param config_path: Path to configuration file
        """
        self.config_path = config_path or self.vm_config_path
        self.vm_name = vm_name
        self._config = self._load_and_merge_config(self.config_path, vm_name)
        self.cpus = self._config.cpus
        self.memory = self._config.memory
        self.audio = self._config.audio
        self.nested_virtualization = self._config.nested_virtualization
        self.speculative_execution_control = self._config.speculative_execution_control
        self.network = self._config.network
        self.host_adapters = self._get_valid_host_adapters_names()
        self._check_specified_adapter()

    def _check_specified_adapter(self):
        """
        Validates the specified network adapters against available host adapters.

        Raises:
            ValueError: If the adapter specified in the network configuration is not
            found among the valid host adapters. This may occur if the adapter is
            disconnected, not supported, or does not meet criteria (e.g., wireless and not 'Up' status).
        """
        for adapter in self.network:
            if adapter.adapter_name and adapter.adapter_name not in self.host_adapters:
                raise ValueError(
                    f"[red]|ERROR| Adapter '{adapter.adapter_name}' not found on host or not supported. "
                    f"The adapter may have the status 'Up' and not be wireless."
                )

    @staticmethod
    def _load_config(file_path: str) -> ConfigFileModel:
        """
        Loads the complete configuration from a JSON file.

        :param file_path: The path to the configuration JSON file.
        :return: An instance of ConfigFileModel containing the loaded configuration.
        """
        with open(file_path, 'r') as f:
            return ConfigFileModel(**json.load(f))

    @staticmethod
    def _merge_configs(default: SystemConfigModel, specific: VmSpecificConfigModel) -> SystemConfigModel:
        """
        Merges VM-specific configuration with default configuration.
        If VM-specific network is provided, it fully replaces the default network list.
        Missing fields in each adapter config are filled from the default adapter with the same number.

        :param default: Default configuration
        :param specific: VM-specific configuration overrides
        :return: Merged SystemConfigModel instance
        """
        merged_data = default.model_dump()
        specific_data = specific.model_dump(exclude_none=True)

        if 'network' in specific_data and specific_data['network']:
            default_by_number = {
                adapter['adapter_number']: adapter for adapter in merged_data['network']
            }
            merged_adapters = []
            for adapter in specific_data['network']:
                number = adapter.get('adapter_number', 1)
                base = default_by_number.get(number, {}).copy()
                base.update(adapter)
                merged_adapters.append(base)
            merged_data['network'] = merged_adapters
            del specific_data['network']

        merged_data.update(specific_data)
        return SystemConfigModel(**merged_data)

    def _load_and_merge_config(self, file_path: str, vm_name: str = None) -> SystemConfigModel:
        """
        Loads configuration and applies VM-specific overrides if vm_name is provided.

        :param file_path: The path to the configuration JSON file
        :param vm_name: Name of the VM to load specific configuration for
        :return: An instance of SystemConfigModel with merged configuration
        """
        config_file = self._load_config(file_path)

        if vm_name and vm_name in config_file.vm_specific:
            print(f"[cyan]|INFO| Loading VM-specific configuration for '{vm_name}'")
            return self._merge_configs(config_file.default, config_file.vm_specific[vm_name])

        return config_file.default

    def display_config(self):
        """
        Displays the loaded system configuration.
        """
        network_info = "\n".join(
            f"  Adapter {a.adapter_number}: type={a.connect_type}"
            f"{f', name={a.adapter_name}' if a.adapter_name else ''}"
            for a in self.network
        )
        print(
            f"[green]|INFO| System Configuration:\n"
            f"  CPUs: {self.cpus}\n"
            f"  Memory: {self.memory}MB\n"
            f"  Audio Enabled: {self.audio}\n"
            f"  Nested Virtualization: {self.nested_virtualization}\n"
            f"  Speculative Execution Control: {self.speculative_execution_control}\n"
            f"{network_info}"
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
        If vm_name is specified, updates VM-specific configuration; otherwise updates default.

        :param kwargs: Key-value pairs to update in the configuration.
        """
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
            else:
                raise AttributeError(f"Invalid configuration key: {key}")

        config_file = self._load_config(self.config_path)

        if self.vm_name:
            if self.vm_name in config_file.vm_specific:
                vm_config_data = config_file.vm_specific[self.vm_name].model_dump(exclude_none=True)
                for key, value in kwargs.items():
                    vm_config_data[key] = value
                config_file.vm_specific[self.vm_name] = VmSpecificConfigModel(**vm_config_data)
            else:
                vm_config_data = {}
                for key, value in kwargs.items():
                    vm_config_data[key] = value
                config_file.vm_specific[self.vm_name] = VmSpecificConfigModel(**vm_config_data)
        else:
            config_file.default = self._config

        with open(self.config_path, 'w') as file:
            json.dump(config_file.model_dump(exclude_none=True), file, indent=2)
