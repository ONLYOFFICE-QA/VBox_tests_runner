# -*- coding: utf-8 -*-
from functools import wraps

from VBoxWrapper import VirtualMachine

from frameworks.decorators import vm_is_turn_on
from .vm_data import VmData
from .configs import VmConfig


def class_cache(class_):
    __instances = {}

    @wraps(class_)
    def wrapper(*args, **kwargs):
        key = (class_, args, frozenset(kwargs.items()))
        if key not in __instances:
            __instances[key] = class_(*args, **kwargs)
        return __instances[key]

    return wrapper

@class_cache
class VboxMachine:

    def __init__(self, name: str, config_path: str = None):
        self.vm_config = VmConfig(config_path=config_path)
        self.vm = VirtualMachine(name)
        self.name = name
        self.data = None
        self.__os_type = None

    @vm_is_turn_on
    def create_data(self):
        self.data = VmData(
            ip=self.vm.network.get_ip(),
            user=self.vm.get_logged_user(),
            name=self.name,
            local_dir=self.vm.get_parameter('CfgFile')
        )

    @property
    def os_type(self) -> str:
        if self.__os_type is None:
            self.__os_type = self.vm.get_os_type().lower()

        return self.__os_type

    def run(self, headless: bool = True, status_bar: bool = False, timeout: int = 600):
        if self.vm.power_status():
            self.vm.stop()

        self.vm.snapshot.restore()
        self.configurate()
        self.vm.run(headless=headless)
        self.vm.network.wait_up(status_bar=status_bar, timeout=timeout)
        self.vm.wait_logged_user(status_bar=status_bar, timeout=timeout)
        self.create_data()

    def configurate(self):
        self.vm.set_cpus(self._get_cpu_num())
        self.vm.nested_virtualization(self.vm_config.nested_virtualization)
        self.vm.set_memory(self.vm_config.memory)
        self.vm.audio(self.vm_config.audio)
        self.vm.speculative_execution_control(self.vm_config.speculative_execution_control)

    def stop(self):
        self.vm.stop()

    def _get_cpu_num(self) -> int:
        # if 'vista' in self.os_type:
        #     return 1
        return self.vm_config.cpus
