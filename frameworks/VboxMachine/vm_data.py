# -*- coding: utf-8 -*-
from dataclasses import dataclass


@dataclass
class VmData:
    """
    Data container for VM connection and configuration information.

    :param user: Username for VM login
    :param ip: IP address of the VM
    :param name: VM name identifier
    :param local_dir: Local directory path for VM configuration
    """
    user: str
    ip: str
    name: str
    local_dir: str
