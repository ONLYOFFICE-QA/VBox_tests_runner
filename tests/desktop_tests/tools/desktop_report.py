# -*- coding: utf-8 -*-
import concurrent.futures
import re
from os.path import isfile, basename
from os.path import dirname
from typing import Optional

import pandas as pd
from host_tools.utils import Dir
from rich import print
from rich.console import Console

from host_tools import File, HostInfo
from frameworks.report import Report
from telegram import Telegram

from frameworks.report_portal import PortalManager
from frameworks.test_data import PortalData


class DesktopReport:

    def __init__(self, report_path: str):
        self.path = report_path
        self.dir = dirname(self.path)
        self.report = Report()
        self.console = Console()
        self.portal_data = PortalData()
        self.host = HostInfo()
        Dir.create(self.dir, stdout=False)

    def write(self, version: str, vm_name: str, exit_code: str) -> None:
        self._write_titles() if not isfile(self.path) else ...
        self._writer(mode='a', message=[vm_name, vm_name, str(version), 'NONE', exit_code, exit_code])

    def get_total_count(self, column_name: str) -> int:
        return self.report.total_count(self.report.read(self.path), column_name)


    def get_error_vm_list(self) -> list[str]:
        if not isfile(self.path):
            raise FileNotFoundError(f"[red]|ERROR| Report not found: {self.path}")

        df = self.report.read(self.path)
        return df[df['Exit_code'] != 'Passed']['Vm_name'].unique()

    def get_reported_vm_names(self, df: Optional[pd.DataFrame] = None) -> list[str]:
        """
        Returns VM names from the report.
        :param df: Optional report DataFrame.
        :return: List of VM names.
        """
        if df is None:
            if not isfile(self.path):
                raise FileNotFoundError(f"[red]|ERROR| Report not found: {self.path}")
            df = self.report.read(self.path)

        if df.empty or 'Vm_name' not in df.columns:
            return []

        vm_names = df['Vm_name'].dropna().astype(str).map(str.strip)
        return self._unique_preserve_order([name for name in vm_names if name])

    def get_missing_vm_names(self, expected_vm_names: list[str], df: Optional[pd.DataFrame] = None) -> list[str]:
        """
        Returns expected VM names missing in the report.
        :param expected_vm_names: List of expected VM names.
        :param df: Optional report DataFrame.
        :return: List of missing VM names.
        """
        if not expected_vm_names:
            return []

        expected_clean = [str(name).strip() for name in expected_vm_names if name]
        if not expected_clean:
            return []

        reported_vm_names = set(self.get_reported_vm_names(df=df))
        missing_vm_names = [name for name in expected_clean if name not in reported_vm_names]
        return self._unique_preserve_order(missing_vm_names)

    def get_full(self, version: str) -> str:
        File.delete(self.path, stdout=False) if isfile(self.path) else ...
        self.report.merge(
            File.get_paths(self.dir, name_include=f"{version}", extension='csv'),
            self.path
        )
        return self.path

    def insert_vm_name(self, vm_name: str) -> None:
        self.report.save_csv(
            self.report.insert_column(self.path, location='Version', column_name='Vm_name', value=vm_name),
            self.path
        )

    def column_is_empty(self, column_name: str) -> bool:
        if not self.report.read(self.path)[column_name].count() or not isfile(self.path):
            return True
        return False

    def _get_version(self, df):
        """
        Get version from DataFrame or fallback to filename.

        :param df: Report DataFrame
        :return: Version string
        """
        if df.empty:
            raise ValueError("Report is empty")

        # Filter only non-empty versions
        valid_versions = df['Version'].dropna()
        valid_versions = valid_versions[valid_versions.astype(str).str.strip() != '']

        if not valid_versions.empty:
            unique_versions = valid_versions.unique()
            if len(unique_versions) > 1:
                print("[red]|WARNING| Versions is not unique.")
            return str(unique_versions[-1])

        # Fallback: extract version from filename (e.g., "9.3.0.98_ONLYOFFICE_...")
        filename = basename(self.path)
        match = re.match(r'^(\d+\.\d+\.\d+\.\d+)', filename)
        if match:
            return match.group(1)

        raise ValueError(f"Version not found in report or filename: {self.path}")

    def send_to_report_portal(self, project_name: str, packege_name: str):
        df = self.report.read(self.path).dropna(how='all')
        version = self._get_version(df)

        if df.empty:
            raise ValueError(f"Report is empty: {self.path}")

        print(f"[green]|INFO| Starting sending to report portal for version: {version}...")
        with PortalManager(project_name=project_name, launch_name=version) as launch:
            self._create_suites(df, launch, packege_name)

            with self.console.status('') as status:
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(self._process_row, row, launch, packege_name) for _, row in df.iterrows()]
                    for future in concurrent.futures.as_completed(futures):
                        future.add_done_callback(lambda *_: status.update(self._get_thread_result(future)))

                    concurrent.futures.wait(futures)

    @staticmethod
    def is_passed(row: pd.Series) -> bool:
        return row['Exit_code'] == 'Passed'

    def _process_row(self, row: pd.Series, launch: PortalManager, package_name: str) -> Optional[str]:
        launch.set_test_result(
            test_name=row['Test_name'],
            return_code=0 if self.is_passed(row) else 1,
            log_message=row['Exit_code'] if not self.is_passed(row) else None,
            suite_uuid=self._create_suite(self._get_os_name(row), launch, package_name),
            status=self.portal_data.get_status(row['Exit_code'])
        )

        if not self.is_passed(row):
            self.console.print(
                f"[bold red]|ERROR| [cyan]{row['Test_name']}[/] failed. Exit_Code: {row['Exit_code']}"
            )
            return ''
        return f"[cyan][{'green'}][{row['Os']}] {row['Test_name']} finished with exit code {row['Exit_code']}"

    def _create_suites(self, df: pd.DataFrame, launch: PortalManager, packege_name: str):
        with self.console.status('') as status:
            for _, row in df.iterrows():
                os = self._get_os_name(row)
                status.update(f"[cyan]|INFO| Created suite {os} launchers for {row['Version']} test.")
                self._create_suite(os, launch, packege_name)

    @staticmethod
    def _create_suite(os_name: str, launch: PortalManager, packege_name: str) -> str:
        return launch.create_suite(os_name, parent_suite_uuid=launch.create_suite(packege_name))

    @staticmethod
    def _get_os_name(row: pd.Series) -> str:
        return f"{row['Os']} (VM: {row['Vm_name']})"

    def exists(self) -> bool:
        return isfile(self.path)

    def send_to_tg(self, data) -> None:
        """
        Send report to Telegram.
        :param data: DesktopTestData instance.
        :param expected_vm_names: List of expected VM names to validate report completeness.
        :return: None
        """
        if not isfile(self.path):
            return print(f"[red]|ERROR| Report for sending to telegram not exists: {self.path}")

        update_info = f"{data.update_from} -> " if data.update_from else ""
        df = self.report.read(self.path)

        main_result_line = self._get_overall_result(df)
        package_not_exists_os = self._get_os_list_by_status(df, self.portal_data.test_status.not_exists_package)
        failed_create_vm_os = self._get_os_list_by_status(df, self.portal_data.test_status.failed_create_vm)

        missing_vm_names = (
            self.get_missing_vm_names(data.vm_names, df=df)
            if data.vm_names
            else []
        )

        caption_parts = [
            f"{data.title} desktop editor tests completed on version: `{update_info}{data.version}`\n\n",
            f"Package: `{data.package_name}`\n",
            f"Result: `{main_result_line}`\n"
        ]
        if package_not_exists_os:
            caption_parts.append(f"Package not exists for OS: `{', '.join(package_not_exists_os)}`\n\n")

        if failed_create_vm_os:
            caption_parts.append(f"Failed to create VM for OS: `{', '.join(failed_create_vm_os)}`\n\n")

        if missing_vm_names:
            caption_parts.append(f"Missing VMs in report: `{', '.join(missing_vm_names)}`\n\n")

        caption_parts.append(f"Number of tested Os: `{self.get_total_count('Exit_code')}`\n")
        caption_parts.append(f"Host: `{self.host.name(pretty=True)} {self.host.arch}`")
        caption = ''.join(caption_parts)
        tg = Telegram(token=data.tg_token, chat_id=data.tg_chat_id)
        tg.send_document(self.path, caption=caption)

        if data.tg_report_chat_id:
            Telegram(token=data.tg_token, chat_id=data.tg_report_chat_id).send_document(self.path, caption=caption)

    def _get_os_list_by_status(self, df: pd.DataFrame, status: str):
        """
        Returns a list of OS names where Exit_code matches the given status.
        :param status: The status to filter by.
        :return: List of OS names.
        """
        filtered_df = df[df['Exit_code'] == status]
        return list(filtered_df['Vm_name'].unique()) if not filtered_df.empty else []

    def _get_overall_result(self, df: pd.DataFrame):
        """
        Returns overall test result status for all except PACKAGE_NOT_EXISTS.
        :return: String with test result status.
        """
        results = df[
            (df['Exit_code'] != self.portal_data.test_status.not_exists_package) &
            (df['Exit_code'] != self.portal_data.test_status.failed_create_vm)
        ]
        return 'All tests passed' if not results.empty and results['Exit_code'].eq('Passed').all() else 'Some tests have errors'

    def _writer(self, mode: str, message: list, delimiter='\t', encoding='utf-8'):
        self.report.write(self.path, mode, message, delimiter, encoding)

    def _write_titles(self):
        self._writer(mode='w', message=['Os', 'Vm_name', 'Version', 'Test_name', 'Package_name', 'Exit_code'])

    @staticmethod
    def _unique_preserve_order(items: list[str]) -> list[str]:
        """
        Remove duplicates while preserving order.
        :param items: List of items.
        :return: Unique list.
        """
        result = []
        seen = set()
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    @staticmethod
    def _get_thread_result(future):
        """
        Gets the result of a thread execution.
        :param future: The future object representing the result of a thread.
        :return: The result of the thread execution.
        """
        try:
            return future.result()
        except (PermissionError, FileExistsError, NotADirectoryError, IsADirectoryError) as e:
            return f"[red]|ERROR| Exception when getting result {e}"
