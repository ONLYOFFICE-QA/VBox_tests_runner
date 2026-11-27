# -*- coding: utf-8 -*-
import re
import subprocess
from vboxwrapper import VirtualMachine

from frameworks.decorators import vm_is_turn_on, class_cache
from .vm_data import VmData
from .configs import VmConfig
from host_tools import HostInfo


@class_cache
class VboxMachine:
    """
    VirtualBox machine wrapper providing high-level operations and configuration management.

    This class provides a simplified interface for managing VirtualBox VMs with
    automatic configuration, network setup, and data management capabilities.
    """

    stale_guest_properties = (
        '/VirtualBox/GuestInfo/Net/0/V4/IP',          # vboxwrapper Network.get_ip / wait_up
        '/VirtualBox/GuestInfo/OS/LoggedInUsersList',  # vboxwrapper VirtualMachine.get_logged_user / wait_logged_user
    )

    def __init__(self, name: str, config_path: str = None):
        """
        Initialize VboxMachine with specified VM name and optional configuration.

        :param name: Name of the VirtualBox virtual machine
        :param config_path: Optional path to configuration file
        """
        self.host = HostInfo()
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
            prefix = 'arm64' if 'arm64' in self.vm.name.lower() else ''
            if prefix:
                self.__os_name += f' {prefix}'
        return self.__os_name

    def run(
        self,
        headless: bool = True,
        status_bar: bool = False,
        timeout: int = 600,
        restore_snapshot: bool = True,
        snapshot_name: str = None,
        configurate: bool = True
    ):
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

        if restore_snapshot:
            self.vm.snapshot.restore(name=snapshot_name)

        if configurate:
            self.configurate()

        resumes_saved_state = (self.vm.get_parameter('VMState') or '').lower() == 'saved'
        self.vm.run(headless=headless)
        if not resumes_saved_state:
            # a guest resumed from a saved state is up already: its properties are current and are not published
            # again, deleting them would leave the waits below nothing to wait for
            self.clear_guest_info()
        self.vm.network.wait_up(status_bar=status_bar, timeout=timeout)
        self.vm.wait_logged_user(status_bar=status_bar, timeout=timeout)
        self.create_data()

    def clear_guest_info(self) -> None:
        """
        Delete the guest properties the VM was started with, so that the waits for the network and the logged user
        get what this boot of the guest reports.

        A snapshot keeps the guest properties of the moment it was taken: right after the start the VM answers
        with the IP it had then - by now maybe the address of another VM of the network (Kubuntu22 started with
        192.168.0.120 of Ubuntu20 and reported its own 192.168.0.121 20 s later) - and with its logged user
        before the guest has even booted. The Guest Additions publish both again once the guest is up.
        """
        for prop in self.stale_guest_properties:
            subprocess.run(
                ['vboxmanage', 'guestproperty', 'delete', self.name, prop],
                capture_output=True, text=True, check=False
            )

    def configurate(self):
        """
        Apply VM configuration including network, CPU, memory and other settings.

        Configures network adapter, CPU count, nested virtualization,
        memory allocation, audio settings, and speculative execution control.
        """
        if not self.host.is_arm:
            # USB 2.0 (EHCI) and USB 3.0 (xHCI) controllers are disabled for non-ARM64 VMs because UsbNet is used for NAT networking
            self.vm.usb.ehci_controller(False)
            self.vm.usb.xhci_controller(False)
            self.vm.usb.controller(False)

        self.set_network_adapter()
        self.vm.set_cpus(self._get_cpu_num())

        if not self.host.is_mac:
            self.vm.nested_virtualization(self.vm_config.nested_virtualization)

        self.vm.set_memory(self._get_memory_num())
        self.vm.audio(self.vm_config.audio)

        if not self.host.is_arm:
            self.vm.speculative_execution_control(self.vm_config.speculative_execution_control)

    def stop(self):
        """
        Stop the virtual machine.
        """
        self.vm.stop()

    def set_network_adapter(self) -> None:
        """
        Configure VM network adapters based on configuration settings.

        Iterates over the list of network adapter configurations and sets
        each adapter accordingly. For bridged adapters, selects the appropriate
        host adapter if not explicitly specified.
        """
        host_adapters = self.vm_config.host_adapters

        for adapter_config in self.vm_config.network:
            adapter_name = adapter_config.adapter_name
            connect_type = adapter_config.connect_type
            adapter_number = adapter_config.adapter_number

            if connect_type == "bridged":
                if adapter_name and adapter_name != self.adapter_name:
                    pass
                elif not adapter_name:
                    if host_adapters and self.adapter_name not in host_adapters:
                        adapter_name = host_adapters[0]
                    else:
                        adapter_name = self.adapter_name

            self.vm.network.set_adapter(
                turn=True,
                adapter_number=adapter_number,
                adapter_name=adapter_name if connect_type == "bridged" else None,
                connect_type=connect_type
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
