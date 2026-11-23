# -*- coding: utf-8 -*-
import json
from os.path import isfile, dirname, join, basename
from typing import Optional

import pandas as pd
from host_tools import File, HostInfo
from host_tools.utils import Dir
from rich import print
from telegram import Telegram

from frameworks.test_data import PortalData


class PuppeteerReport:
    """
    CSV report (tab-separated) of the Dep.Tests/puppeteer desktop tests: one row per test per VM, built from the
    launch record run.py writes (``out/<build>/native/launches/<time>.json``), merged over all VMs and sent to
    Telegram.

    The rows hold free text from run.py (test paths, failure reasons, some of them not ASCII), so the report is
    read and written with pandas directly, not through frameworks.report.Report, which drops a last row with
    non-ASCII text and rewrites the file.
    """

    columns = ['Os', 'Vm_name', 'Version', 'Test_name', 'Status', 'Reason', 'Duration_ms', 'Run_dir']
    passed_status = 'passed'
    warning_status = 'warning'
    failed_status = 'failed'
    ok_statuses = (passed_status, warning_status)
    """A test that passed with a warning of the editor (run.py WARNING_RETURN_CODE) is not a failure."""
    run_py_test_name = 'run.py'
    vm_report_suffix = '_vm_report.csv'
    caption_limit = 1000
    """Caption length the telegram package sends whole (MAX_CAPTCHA_LENGTH)."""

    def __init__(self, report_path: str):
        self.path = report_path
        self.dir = dirname(self.path)
        self.portal_data = PortalData()
        Dir.create(self.dir, stdout=False)

    def exists(self) -> bool:
        return isfile(self.path)

    @staticmethod
    def find_launch_record(out_dir: str) -> Optional[str]:
        """
        The latest launch record of a native run in the downloaded ``out`` folder.

        :param out_dir: Local copy of ``puppeteer/out``
        :return: Path to the launch JSON or None
        """
        records = [
            path for path in File.get_paths(out_dir, extension='json')
            if basename(dirname(path)) == 'launches' and basename(dirname(dirname(path))) == 'native'
        ]
        if not records:
            return None
        return max(records, key=lambda path: json.loads(File.read(path)).get('started') or '')

    def write_from_launch(self, launch_record: str, os_name: str, vm_name: str, version: str) -> int:
        """
        Write the tests of a launch record as the rows of this report, plus a failed ``run.py`` row when the
        launch is not complete: it ended with an error, did not finish (run.py was killed), ran fewer tests than
        planned or none at all.

        :return: Number of tests written
        """
        launch = json.loads(File.read(launch_record))
        tests = launch.get('tests') or []
        rows = [
            [
                os_name,
                vm_name,
                str(version),
                test.get('test', ''),
                test.get('status', ''),
                self._one_line(test.get('reason')),
                test.get('ms', ''),
                test.get('run', ''),
            ]
            for test in tests
        ]

        problem = self._launch_problem(launch, tests)
        if problem:
            rows.append(self._run_py_row(os_name, vm_name, version, problem))

        self._save(pd.DataFrame(rows, columns=self.columns), mode='w')
        return len(tests)

    def write_run_error(self, os_name: str, vm_name: str, version: str, reason: str) -> None:
        """Write a failed ``run.py`` row: run.py stopped before it recorded a launch (see ``out/vm_run.log``)."""
        self._save(pd.DataFrame([self._run_py_row(os_name, vm_name, version, reason)], columns=self.columns), mode='w')

    def write_status(self, os_name: str, vm_name: str, version: str, status: str) -> None:
        """Write one row for a VM whose tests did not run (e.g. FAILED_CREATE_VM)."""
        row = [os_name, vm_name, str(version), 'NONE', status, status, '', '']
        self._save(pd.DataFrame([row], columns=self.columns), mode='a' if self.exists() else 'w')

    def get_full(self, version: str) -> Optional[str]:
        """Merge the VM reports of the version folder into this report."""
        if isfile(self.path):
            File.delete(self.path, stdout=False)
        reports = [
            path for path in File.get_paths(self.dir, name_include=str(version), extension='csv')
            if path.endswith(self.vm_report_suffix)
        ]
        if not reports:
            print(f"[red]|ERROR| No VM reports found in {self.dir}")
            return None
        self._save(pd.concat([self.read(path) for path in reports], ignore_index=True), mode='w')
        return self.path

    def read(self, path: Optional[str] = None) -> pd.DataFrame:
        return pd.read_csv(path or self.path, sep='\t', dtype=str, keep_default_na=False, encoding='utf-8')

    def get_error_vm_list(self, df: Optional[pd.DataFrame] = None) -> list[str]:
        df = self.read() if df is None else df
        return list(df[~df['Status'].isin(self.ok_statuses)]['Vm_name'].unique())

    def get_missing_vm_names(self, expected_vm_names: list[str], df: Optional[pd.DataFrame] = None) -> list[str]:
        """The expected VMs that left no row in the report."""
        df = self.read() if df is None else df
        reported = set(df['Vm_name'].str.strip()) if not df.empty else set()
        expected = dict.fromkeys(str(name).strip() for name in expected_vm_names if name)
        return [name for name in expected if name not in reported]

    def send_to_tg(self, data) -> None:
        """
        Send the merged report to Telegram with a per-VM summary in the caption, and the failed tests apart.

        :param data: PuppeteerTestData
        """
        if not self.exists():
            return print(f"[red]|ERROR| Report for sending to telegram not exists: {self.path}")

        caption = self.get_caption(data)
        errors_report = self._write_errors_only()
        chat_ids = [data.tg_chat_id] + ([data.tg_report_chat_id] if data.tg_report_chat_id else [])
        for chat_id in chat_ids:
            tg = Telegram(token=data.tg_token, chat_id=chat_id)
            tg.send_document(self.path, caption=caption)
            if errors_report:
                tg.send_document(errors_report, caption=f"Failed tests on version: `{data.version}`")

    def get_caption(self, data) -> str:
        df = self.read()
        tested = df[~df['Status'].isin(self.portal_data.test_status.skipped_tuple)]
        tests = tested[tested['Test_name'] != self.run_py_test_name]
        ok = tests['Status'].isin(self.ok_statuses)
        warnings = int(tests['Status'].eq(self.warning_status).sum())
        failed_vm = list(df[df['Status'] == self.portal_data.test_status.failed_create_vm]['Vm_name'].unique())
        missing = self.get_missing_vm_names(data.vm_names, df=df)
        error_vms = self.get_error_vm_list(df=df)

        head = [
            f"{data.title} DesktopEditors puppeteer tests completed on version: `{data.version}`\n",
            f"Suite: `{data.test_path or data.suite}`\n",
            f"Result: `{'All tests passed' if not tested.empty and not error_vms and not missing else 'Some tests have errors'}`\n",
            f"Tests: `{len(tests)}`, passed: `{int(ok.sum())}`"
            f"{f' (with warnings: `{warnings}`)' if warnings else ''}, failed: `{int((~ok).sum())}`\n\n",
        ]
        vm_lines = []
        for vm_name, vm_df in tested.groupby('Vm_name', sort=False):
            vm_tests = vm_df[vm_df['Test_name'] != self.run_py_test_name]
            passed = int(vm_tests['Status'].isin(self.ok_statuses).sum())
            not_complete = ' (run.py did not complete)' if (vm_df['Test_name'] == self.run_py_test_name).any() else ''
            vm_lines.append(f"`{vm_name}`: {passed}/{len(vm_tests)} passed{not_complete}\n")

        tail = []
        if failed_vm:
            tail.append(f"\nFailed to create VM: `{', '.join(failed_vm)}`\n")
        if missing:
            tail.append(f"\nMissing VMs in report: `{', '.join(missing)}`\n")
        tail.append(f"\nHost: `{HostInfo().name(pretty=True)} {HostInfo().arch}`")

        return self._fit_caption(head, vm_lines, tail)

    def _fit_caption(self, head: list[str], vm_lines: list[str], tail: list[str]) -> str:
        """Drop whole VM lines (never a part of one: a cut backtick breaks Markdown) until the caption fits."""
        shown = list(vm_lines)
        while shown:
            more = len(vm_lines) - len(shown)
            caption = ''.join([*head, *shown, f"... and {more} more VMs in the report\n" if more else '', *tail])
            if len(caption) <= self.caption_limit:
                return caption
            shown.pop()
        return ''.join([*head, f"{len(vm_lines)} VMs in the report\n", *tail])[:self.caption_limit]

    def _write_errors_only(self) -> Optional[str]:
        df = self.read()
        errors = df[~df['Status'].isin(self.ok_statuses)]
        if errors.empty:
            return None
        errors_path = join(self.dir, f"{basename(self.path).rsplit('.', 1)[0]}_errors_only.csv")
        errors.to_csv(errors_path, sep='\t', index=False, encoding='utf-8')
        return errors_path

    def _save(self, df: pd.DataFrame, mode: str) -> None:
        df.to_csv(self.path, sep='\t', index=False, encoding='utf-8', mode=mode, header=mode == 'w')

    def _run_py_row(self, os_name: str, vm_name: str, version: str, reason: str) -> list:
        return [os_name, vm_name, str(version), self.run_py_test_name, self.failed_status, self._one_line(reason), '', '']

    @staticmethod
    def _launch_problem(launch: dict, tests: list) -> Optional[str]:
        """Why a launch is not complete, or None when it is."""
        planned = launch.get('planned') or 0
        if launch.get('error'):
            return launch['error']
        if launch.get('finished') is None:
            return f"run.py did not finish: {len(tests)} of {planned or '?'} planned tests ran"
        if not tests:
            return "run.py ran no tests"
        if len(tests) < planned:
            return f"only {len(tests)} of {planned} planned tests ran"
        return None

    @staticmethod
    def _one_line(text: Optional[str]) -> str:
        return ' '.join(str(text).split()) if text else ''
