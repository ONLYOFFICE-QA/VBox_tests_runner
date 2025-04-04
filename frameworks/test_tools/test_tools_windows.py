# -*- coding: utf-8 -*-
from VBoxWrapper import VirtualMachinException

from frameworks.decorators import retry, vm_data_created
from .test_tools import TestTools, TestData, VboxMachine
from frameworks.vbox_utils import VboxUtilsVista, VboxUtilsWindows


class TestToolsWindows(TestTools):

    def __init__(self, vm: VboxMachine, test_data: TestData):
        super().__init__(vm=vm, test_data=test_data)
        self.remote_report_dir = None
        self.paths = None
        self.report = None
        self.vbox_utils = None

    @retry(max_attempts=2, exception_type=VirtualMachinException)
    def run_vm(self, headless: bool = False) -> None:
        self.vm.run(headless=False, status_bar=self.data.status_bar)

    def initialize_libs(self, report, paths) -> None:
        self.report = report
        self.paths = paths
        self.remote_report_dir = f"{self.paths.remote.report_dir}/{self.data.title}/{self.data.version}"
        self._initialize_vbox_utils()

    @vm_data_created
    def run_test_on_vm(self,  upload_files: list, create_test_dir: list):
        self.vbox_utils.create_test_dirs(create_test_dir)
        self.vbox_utils.upload_test_files(upload_files)
        self.vbox_utils.run_script_on_vm(status_bar=self.data.status_bar)
        self.download_report()

    def download_report(self):
        if (
                self.vbox_utils.download_report(self.remote_report_dir, self.report.dir)
                and not self.report.column_is_empty("Os")
        ):
            self.report.insert_vm_name(self.vm_name)
        else:
            print(f"[red]|ERROR| Can't download report from {self.vm.data.name}.")

    def _initialize_vbox_utils(self):
        common_params = {
            "vm": self.vm.vm,
            "user_name": self.vm.data.user,
            "password": self._get_password(self.vm.data.local_dir),
            "paths": self.paths,
            "test_data": self.data,
        }

        self.vbox_utils = (
            VboxUtilsVista(**common_params)
            if "vista" in self.vm.os_type
            else VboxUtilsWindows(**common_params)
        )
