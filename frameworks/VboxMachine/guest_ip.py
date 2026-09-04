# -*- coding: utf-8 -*-
"""
Resolution of the guest IPv4 address the host can open a connection to.

VirtualBox NAT gives every guest 10.0.2.15 and is outbound only, so an address reported by Guest
Additions is not necessarily one the host can reach. Waiting for the network of a machine succeeds
on that address as well, which is why the choice of a usable address lives here instead of in the
machine itself.
"""
import ipaddress
import re
import time

from rich import print
from vboxwrapper import VirtualMachine, VirtualMachinException

from .configs import VmConfig

# Guest Additions reports one IPv4 property per NIC; Net/0 is the first adapter, usually NAT.
_GUEST_IPV4_PROPERTY = re.compile(r'^/VirtualBox/GuestInfo/Net/\d+/V4/IP$')
# VirtualBox NAT is outbound-only: the host cannot open TCP to 10.0.2.15.
_UNREACHABLE_GUEST_NETWORKS = (
    ipaddress.ip_network('10.0.2.0/24'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),
)
_HOSTONLY_NETWORK = ipaddress.ip_network('192.168.56.0/24')


def pick_reachable_guest_ip(addresses: list[str]) -> str | None:
    """
    Pick a guest IPv4 that the host can open a TCP session to.

    Skips VirtualBox NAT. Prefers the default host-only network when several
    addresses are present.
    :param addresses: IPv4 addresses reported by Guest Additions.
    :return: Reachable IPv4 string, or None when every address is NAT/loopback.
    """
    reachable: list[str] = []
    for raw in addresses:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if address.version != 4:
            continue
        if any(address in network for network in _UNREACHABLE_GUEST_NETWORKS):
            continue
        reachable.append(str(address))

    for ip in reachable:
        if ipaddress.ip_address(ip) in _HOSTONLY_NETWORK:
            return ip
    return reachable[0] if reachable else None


class GuestIp:
    """
    Reads the addresses Guest Additions reports and picks the one the host can connect to.
    """

    def __init__(self, vm: VirtualMachine, vm_config: VmConfig):
        """
        Initialize the resolver for a single machine.

        :param vm: Machine whose Guest Additions properties are read
        :param vm_config: Configuration of the machine, used to tell how it is connected
        """
        self.vm = vm
        self.vm_config = vm_config

    @property
    def hostonly(self) -> bool:
        """
        Whether the machine has a host-only adapter, which turns a reachable address from a
        preference into a requirement: such machines are reached from the host over SSH.

        :return: True when a host-only adapter is configured
        """
        return any(adapter.connect_type == 'hostonly' for adapter in self.vm_config.network)

    def addresses(self) -> list[str]:
        """
        Collect IPv4 addresses reported by Guest Additions for every NIC.

        :return: Guest IPv4 addresses, possibly including NAT 10.0.2.15
        """
        properties = self.vm.get_guest_properties()
        return [
            value for name, value in properties.items()
            if _GUEST_IPV4_PROPERTY.match(name) and value
        ]

    def get(self) -> str | None:
        """
        Return a host-reachable guest IP when one exists.

        Falls back to Net/0 for NAT-only guests (Windows via guestcontrol).
        :return: Guest IPv4, or None when no address is available
        """
        reachable = pick_reachable_guest_ip(self.addresses())
        if reachable:
            return reachable
        if self.hostonly:
            return None
        return self.vm.network.get_ip()

    def wait_reachable(self, timeout: int = 600, interval: int = 2) -> str:
        """
        Wait until Guest Additions reports an IP the host can connect to.

        wait_up() succeeds on NAT 10.0.2.15, which is not reachable from the host.
        :param timeout: How long to wait in seconds
        :param interval: Pause between polls in seconds
        :return: Reachable guest IPv4
        :raises VirtualMachinException: If no reachable address appears in time
        """
        deadline = time.monotonic() + timeout
        while True:
            ip = pick_reachable_guest_ip(self.addresses())
            if ip:
                print(f"[green]|INFO|{self.vm.name}| Host-reachable guest IP: [cyan]{ip}[/]")
                return ip
            if time.monotonic() >= deadline:
                raise VirtualMachinException(
                    f"[red]|ERROR|{self.vm.name}| Guest has no host-reachable IP after {timeout}s. "
                    f"NAT 10.0.2.0/24 is not reachable from the host."
                )
            print(f"[cyan]|INFO|{self.vm.name}| Waiting for a host-reachable guest IP")
            time.sleep(interval)
