# -*- coding: utf-8 -*-
import re
import time
from os.path import join, dirname, isfile

from rich import print
from vboxwrapper import VirtualMachine, FileUtils

from frameworks.decorators import vm_is_turn_on, class_cache
from .vm_data import VmData
from .configs import VmConfig
from host_tools import HostInfo, File


# VirtualBox adapter number → PCI slot → Linux predictable interface name (enp0s{slot})
_VBOX_PCI_SLOTS = {1: 3, 2: 8, 3: 9, 4: 10, 5: 16, 6: 17, 7: 18, 8: 19}


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
        ip = self._get_management_ip()
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

        self.vm.run(headless=headless)
        self.vm.network.wait_up(status_bar=status_bar, timeout=timeout)
        self.vm.wait_logged_user(status_bar=status_bar, timeout=timeout)
        self._configure_management_interface()
        self._wait_management_network(timeout=timeout, status_bar=status_bar)
        self.create_data()

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
                adapter_name=adapter_name,
                connect_type=connect_type
            )

    def _get_vm_password(self) -> str:
        """Read VM password from the 'password' file next to the .vbox config."""
        vm_dir = self.vm.get_parameter('CfgFile')
        password_file = join(dirname(vm_dir), 'password')
        if isfile(password_file):
            return File.read(password_file).strip()
        raise FileNotFoundError(f"Password file not found: {password_file}")

    def _configure_management_interface(self) -> None:
        """Configure management network interface via DHCP on Linux guests.

        Runs dhclient on the Host-Only/bridged interface if it doesn't
        already have an IP address. Skipped for non-Linux VMs.
        """
        if self.os_type != 'linux':
            return

        adapter = self._get_management_adapter()
        if not adapter:
            return

        if self._get_ip_by_net_index(adapter.adapter_number - 1):
            return

        pci_slot = _VBOX_PCI_SLOTS.get(adapter.adapter_number)
        interface = f"enp0s{pci_slot}" if pci_slot else f"eth{adapter.adapter_number - 1}"

        user = self.vm.get_logged_user()
        password = self._get_vm_password()
        file_utils = FileUtils(vm_id=self.vm, username=user, password=password)

        print(f"[cyan]|INFO|{self.name}| Configuring {interface} with DHCP")
        sudo = f"echo '{password}' | sudo -S"
        file_utils.run_cmd(
            f"{sudo} dhclient {interface} 2>/dev/null",
            shell="/bin/bash -c",
            stdout=False,
            stderr=False
        )

    def _get_management_adapter(self):
        """Find the first non-NAT adapter used for management connections (SSH)."""
        for adapter in self.vm_config.network:
            if adapter.connect_type in ("hostonly", "bridged"):
                return adapter
        return None

    def _get_ip_by_net_index(self, net_index: int) -> str | None:
        """Get IP address from a specific guest network interface.

        :param net_index: Guest network interface index (0-based)
        """
        prop = f"/VirtualBox/GuestInfo/Net/{net_index}/V4/IP"
        output = self.vm._cmd.get_output(
            f'{self.vm._cmd.guestproperty} {self.name} "{prop}"'
        )
        if output and output != 'No value set!':
            return output.split(':')[1].strip()
        return None

    def _get_management_ip(self) -> str | None:
        """Get IP from the management adapter (hostonly/bridged), fallback to Net/0."""
        adapter = self._get_management_adapter()
        if adapter:
            return self._get_ip_by_net_index(adapter.adapter_number - 1)
        return self.vm.network.get_ip()

    def _wait_management_network(self, timeout: int = 600, status_bar: bool = False) -> None:
        """Wait for the management network adapter IP to become available.

        :param timeout: Timeout in seconds
        :param status_bar: Whether to show progress status bar
        """
        adapter = self._get_management_adapter()
        if not adapter:
            return

        net_index = adapter.adapter_number - 1
        msg = (
            f"[cyan]|INFO|{self.name}| Waiting for management network "
            f"(adapter {adapter.adapter_number}, {adapter.connect_type})"
        )
        print(msg)

        start = time.time()
        while time.time() - start < timeout:
            ip = self._get_ip_by_net_index(net_index)
            if ip:
                print(f"[green]|INFO|{self.name}| Management network ready, ip: [cyan]{ip}[/]")
                return
            time.sleep(1)

        raise TimeoutError(
            f"Management network IP not available within {timeout}s "
            f"for adapter {adapter.adapter_number} ({adapter.connect_type})"
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
