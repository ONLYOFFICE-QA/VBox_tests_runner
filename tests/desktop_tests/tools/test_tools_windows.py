# -*- coding: utf-8 -*-
from VBoxWrapper import VirtualMachinException

from frameworks.decorators import retry, vm_data_created
from . import TestTools, TestData, VboxMachine
from .vbox_utils import VboxUtils
from .vbox_utils_vista import VboxUtilsVista


class TestToolsWindows(TestTools):

    def __init__(self, vm: VboxMachine, test_data: TestData):
        super().__init__(vm=vm, test_data=test_data)
        self.vbox_utils = None

    @retry(max_attempts=2, exception_type=VirtualMachinException)
    def run_vm(self, headless: bool = False) -> None:
        self.vm.run(headless=False, status_bar=self.data.status_bar)
        self._initialize_paths()
        self._initialize_run_script()
        self._initialize_vbox_utils()

    @vm_data_created
    def run_test_on_vm(self):
        self.vbox_utils.upload_test_files(self.run_script)
        self.vbox_utils.run_script_on_vm()
        if self.download_and_check_report():
            self.report.insert_vm_name(self.vm_name)

    def download_and_check_report(self):
        if (
                self.vbox_utils.download_report(self.data.title, self.data.version, self.report.dir)
                and not self.report.column_is_empty("Os")
        ):
            return True

        print(f"[red]|ERROR| Can't download report from {self.vm.data.name}.")
        return False

    def _initialize_vbox_utils(self):
        if "vista" in self.vm.os_type:
            self.vbox_utils = VboxUtilsVista(
                vm=self.vm.vm,
                user_name=self.vm.data.user,
                password=self._get_password(self.vm.data.local_dir),
                paths=self.paths,
                test_data=self.data
            )
        else:
            self.vbox_utils = VboxUtils(
                vm=self.vm.vm,
                user_name=self.vm.data.user,
                password=self._get_password(self.vm.data.local_dir),
                paths=self.paths,
                test_data=self.data
            )
