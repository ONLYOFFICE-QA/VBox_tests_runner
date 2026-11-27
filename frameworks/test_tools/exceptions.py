# -*- coding: utf-8 -*-
from vboxwrapper import VirtualMachinException


class VirtualMachinePoweredOff(VirtualMachinException):
    """
    The VM stopped running while a test used it (powered off, or aborted when its VirtualBox process crashed).
    Retrying an SSH or guest command cannot reach it: the step ends at once, and the test's own attempt loop
    starts the VM again.
    """
