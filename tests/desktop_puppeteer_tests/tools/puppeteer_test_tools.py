# -*- coding: utf-8 -*-
import zipfile
from os.path import join, isfile

from host_tools.utils import Dir
from rich import print
from vboxwrapper import VirtualMachinException

from frameworks.VboxMachine import VboxMachine
from frameworks.decorators import vm_data_created
from frameworks.test_data import PortalData
from frameworks.test_tools import TestTools, TestToolsWindows, TestToolsLinux

from .puppeteer_paths import PuppeteerPaths, PuppeteerLocalPaths
from .puppeteer_report import PuppeteerReport
from .puppeteer_test_data import PuppeteerTestData
from .run_script import RunScript


class PuppeteerTestTools:
    """
    Runs the Dep.Tests/puppeteer tests on the Desktop Editors app on one VM: uploads the Dep.Tests archive
    prepared on the host (PuppeteerRepo) with the run script, runs ``run.py --host native`` there, downloads
    ``puppeteer/out`` packed on the VM and unpacks it into ``reports/Desktop_puppeteer_tests/<version>/<vm>/out``,
    converted into a CSV report.
    """

    unsupported_os = ('vista',)
    """Windows Vista runs .bat scripts and no Node.js 20."""
    run_log_tail_lines = 15

    def __init__(self, vm_name: str, test_data: PuppeteerTestData):
        self.data = test_data
        self.portal_data = PortalData()
        self.vm = VboxMachine(vm_name)
        self.test_tools = self._get_test_tools()
        self.paths = None
        self._initialize_report()

    @property
    def out_dir(self) -> str:
        """Local copy of ``puppeteer/out`` of this VM."""
        return join(self.report.dir, 'out')

    @property
    def out_archive_dir(self) -> str:
        """Local folder the packed ``puppeteer/out`` is downloaded into."""
        return join(self.report.dir, 'out_archive')

    def is_supported_os(self) -> bool:
        if any(name in self.vm.os_name for name in self.unsupported_os):
            print(f"[cyan]|INFO|{self.vm.name}| {self.vm.os_name} is not supported by the puppeteer tests (Node.js 20+)")
            return False
        return True

    def run_test(self, headless: bool) -> None:
        self.test_tools.run_vm(headless=headless)
        self.initialize_libs()
        self.test_tools.run_test_on_vm(upload_files=self.get_upload_files(), create_test_dir=self.get_test_dirs())
        self.test_tools.download_report(path_from=self.paths.remote.out_archive_dir, path_to=self.out_archive_dir)

        out_archive = join(self.out_archive_dir, PuppeteerLocalPaths.out_archive_name)
        if not isfile(out_archive):
            # the VM or the setup steps of the script failed: worth another attempt
            raise VirtualMachinException(f"Results of run.py were not packed on the VM: {out_archive} not found")
        self._unpack_out(out_archive)

        launch_record = PuppeteerReport.find_launch_record(self.out_dir)
        if launch_record:
            count = self.report.write_from_launch(
                launch_record=launch_record,
                os_name=self.vm.os_name,
                vm_name=self.vm.name,
                version=str(self.data.version)
            )
            print(f"[green]|INFO|{self.vm.name}| {count} test results saved to [cyan]{self.report.path}[/]")
            return

        # run.py ran and stopped before it recorded a launch (no Node.js, the build not published, ...):
        # another attempt ends the same way, the reason is in its log
        reason = self._run_log_tail()
        self.report.write_run_error(
            os_name=self.vm.os_name,
            vm_name=self.vm.name,
            version=str(self.data.version),
            reason=reason
        )
        print(f"[bold red]|ERROR|{self.vm.name}| run.py recorded no launch: {reason}")

    def handle_vm_creation_failure(self) -> None:
        print(f"[bold red]|ERROR|{self.vm.name}| Failed to create a virtual machine")
        self.report.write_status(
            os_name=self.vm.name,
            vm_name=self.vm.name,
            version=str(self.data.version),
            status=self.portal_data.test_status.failed_create_vm
        )

    def get_upload_files(self) -> list[tuple[str, str]]:
        files = [
            (RunScript(test_data=self.data, paths=self.paths).create(), self.paths.remote.script_path),
            (self.paths.local.dep_test_archive, self.paths.remote.dep_test_archive),
        ]
        return [file for file in files if all(file)]

    def get_test_dirs(self) -> list[str]:
        return [self.paths.remote.script_dir]

    @property
    def is_windows(self) -> bool:
        return self.test_tools.is_windows

    def initialize_libs(self) -> None:
        self.test_tools.initialize_libs(
            report=self._initialize_report(),
            paths=self._initialize_paths(),
        )

    def _unpack_out(self, out_archive: str) -> None:
        """
        Unpack ``out/`` next to the VM report. A file whose path is too long for this host is skipped with a
        warning: the launch record and the run log, which the report is built from, have short paths.
        """
        skipped = []
        with zipfile.ZipFile(out_archive) as archive:
            for member in archive.infolist():
                try:
                    archive.extract(member, self.report.dir)
                except OSError:
                    skipped.append(member.filename)
        if skipped:
            print(f"[yellow]|WARNING|{self.vm.name}| {len(skipped)} files of {out_archive} not unpacked, e.g. {skipped[0]}")

    def _run_log_tail(self) -> str:
        run_log = join(self.out_dir, RunScript.run_log_name)
        if not isfile(run_log):
            return f"run.py recorded no launch and left no {RunScript.run_log_name}"
        with open(run_log, encoding='utf-8', errors='replace') as file:
            lines = [line.strip() for line in file if line.strip()]
        if not lines:
            return f"run.py recorded no launch, {RunScript.run_log_name} is empty"
        return ' | '.join(lines[-self.run_log_tail_lines:])

    def _initialize_report(self) -> PuppeteerReport:
        report_file = join(
            self.data.report_dir,
            self.vm.name,
            f"{self.data.version}_{self.data.title}{PuppeteerReport.vm_report_suffix}"
        )
        self.report = PuppeteerReport(report_file)
        Dir.delete(self.report.dir, clear_dir=True, stdout=False)
        return self.report

    @vm_data_created
    def _initialize_paths(self) -> PuppeteerPaths:
        self.paths = PuppeteerPaths(os_info=self.vm.os_info, remote_user_name=self.vm.data.user)
        return self.paths

    def _get_test_tools(self) -> TestTools:
        if 'windows' in self.vm.os_type:
            return TestToolsWindows(vm=self.vm, test_data=self.data)
        return TestToolsLinux(vm=self.vm, test_data=self.data)
