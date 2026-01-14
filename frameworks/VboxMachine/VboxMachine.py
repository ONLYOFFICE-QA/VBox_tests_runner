# -*- coding: utf-8 -*-
import re
from host_tools import HostInfo
from vboxwrapper import VirtualMachine

from frameworks.decorators import vm_is_turn_on, class_cache
from .vm_data import VmData
from .configs import VmConfig


@class_cache
class VboxMachine:
    """
    VirtualBox machine wrapper providing high-level operations and configuration management.

    This class provides a simplified interface for managing VirtualBox VMs with
    automatic configuration, network setup, and data management capabilities.
    """

    def __init__(self, name: str, config_path: str = None):
        """
        Initialize VboxMachine with specified VM name and optional configuration.

        :param name: Name of the VirtualBox virtual machine
        :param config_path: Optional path to configuration file
        """
        self.name = name
        self.vm_config = VmConfig(vm_name=name, config_path=config_path)
        self.vm = VirtualMachine(name)
        self.data = None
        self.__os_type = None
        self.__adapter_name = None
        self.__os_name = None

    @vm_is_turn_on
    def create_data(self):
        """
        Create VM data object with network and user information.

        Collects VM's IP address, logged user, and configuration file path
        to create a VmData object for further operations.

        :raises ValueError: If IP address or logged user is not available
        """
        ip = self.vm.network.get_ip()
        if ip is None:
            raise ValueError("IP address is not available")

        user = self.vm.get_logged_user()
        if user is None:
            raise ValueError("Logged user is not available")

        self.data = VmData(
            ip=ip,
            user=user,
            name=self.name,
            local_dir=self.vm.get_parameter('CfgFile')
        )

    @property
    def adapter_name(self) -> str:
        """
        Get the name of the bridge adapter used by the VM.

        :return: Bridge adapter name
        """
        if self.__adapter_name is None:
            self.__adapter_name = self.vm.get_parameter('bridgeadapter1')
        return self.__adapter_name

    @property
    def os_type(self) -> str:
        """
        Get the operating system type of the VM.

        :return: OS type ('windows', 'linux', or 'unknown')
        """
        if self.__os_type is None:
            type = self.vm.get_os_type().lower()
            if 'windows' in type:
                self.__os_type = 'windows'
            elif 'linux' in type:
                self.__os_type = 'linux'
            else:
                self.__os_type = 'unknown'
        return self.__os_type

    @property
    def os_info(self) -> dict:
        """
        Get comprehensive OS information including type and name.

        :return: Dictionary containing OS type and name
        """
        return {
            'type': self.os_type,
            'name': self.os_name
        }

    @property
    def os_name(self) -> str:
        """
        Get the detailed OS name without bit information.

        :return: OS name with bit information removed
        :raises ValueError: If OS type is not available
        """
        if self.__os_name is None:
            os_type = self.vm.get_parameter('ostype')
            if os_type is None:
                raise ValueError("OS type is not available")
            self.__os_name = re.sub(r' \([^)]*bit\)', '', os_type).lower()
        return self.__os_name

    def run(self, headless: bool = True, status_bar: bool = False, timeout: int = 600):
        """
        Start the VM with proper configuration and wait for readiness.

        Stops existing VM if running, restores snapshot, applies configuration,
        starts VM, and waits for network and user login.

        :param headless: Whether to run VM in headless mode
        :param status_bar: Whether to show progress status bar
        :param timeout: Timeout in seconds for network and user readiness
        """
        if self.vm.power_status():
            self.vm.stop()

        self.vm.snapshot.restore()
        self.configurate()
        self.vm.run(headless=headless)
        self.vm.network.wait_up(status_bar=status_bar, timeout=timeout)
        self.vm.wait_logged_user(status_bar=status_bar, timeout=timeout)
        self.create_data()

    def configurate(self):
        """
        Apply VM configuration including network, CPU, memory and other settings.

        Configures network adapter, CPU count, nested virtualization,
        memory allocation, audio settings, and speculative execution control.
        """
        self.set_network_adapter()
        self.vm.set_cpus(self._get_cpu_num())
        self.vm.nested_virtualization(self.vm_config.nested_virtualization)
        self.vm.set_memory(self._get_memory_num())
        self.vm.audio(self.vm_config.audio)
        self.vm.speculative_execution_control(self.vm_config.speculative_execution_control)

    def stop(self):
        """
        Stop the virtual machine.
        """
        self.vm.stop()

    def set_network_adapter(self) -> None:
        """
        Configure VM network adapter based on configuration settings.

        Sets network adapter based on specified configuration or selects
        the first available host adapter if current one is not suitable.
        """
        specified = self.vm_config.network.adapter_name
        host_adapters = self.vm_config.host_adapters
        target_adapter = None

        if specified and specified != self.adapter_name:
            target_adapter = specified
        elif not specified:
            if host_adapters and self.adapter_name not in host_adapters:
                target_adapter = host_adapters[0]

        if target_adapter:
            self.vm.network.set_adapter(
                turn=True,
                adapter_name=target_adapter,
                connect_type=self.vm_config.network.connect_type
            )

    def _get_memory_num(self) -> int:
        """
        Get memory allocation for the VM based on host OS and configuration.

        :return: Memory allocation in MB
        """
        return self.vm_config.memory

    def _get_cpu_num(self) -> int:
        """
        Get CPU count configuration for the VM.

        :return: Number of CPU cores to assign to VM
        """
        return self.vm_config.cpus
