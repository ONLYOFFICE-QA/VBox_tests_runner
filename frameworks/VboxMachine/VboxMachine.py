# -*- coding: utf-8 -*-
from VBoxWrapper import VirtualMachine

from frameworks.decorators import vm_is_turn_on
from .vm_data import VmData
from .configs import VmConfig


class VboxMachine:

    def __init__(self, name: str, config_path: str = None):
        self.vm_config = VmConfig(config_path=config_path)
        self.vm = VirtualMachine(name)
        self.name = name
        self.data = None

    @vm_is_turn_on
    def create_data(self):
        self.data = VmData(
            ip=self.vm.network.get_ip(),
            user=self.vm.get_logged_user(),
            name=self.name,
            local_dir=self.vm.get_parameter('CfgFile')
        )

    def get_os_type(self) -> str:
        return self.vm.get_os_type().lower()

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
        self.vm.set_cpus(self.vm_config.cpus)
        self.vm.nested_virtualization(self.vm_config.nested_virtualization)
        self.vm.set_memory(self.vm_config.memory)
        self.vm.audio(self.vm_config.audio)
        self.vm.speculative_execution_control(self.vm_config.speculative_execution_control)

    def stop(self):
        self.vm.stop()
