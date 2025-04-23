# -*- coding: utf-8 -*-
import concurrent.futures
from os.path import isfile
from os.path import dirname
from typing import Optional

import pandas as pd
from host_tools.utils import Dir
from rich import print
from rich.console import Console

from host_tools import File
from frameworks.report import Report
from telegram import Telegram

from frameworks.report_portal import PortalManager


class DesktopReport:

    def __init__(self, report_path: str):
        self.path = report_path
        self.dir = dirname(self.path)
        self.report = Report()
        self.console = Console()
        Dir.create(self.dir, stdout=False)

    def write(self, version: str, vm_name: str, exit_code: str) -> None:
        self._write_titles() if not isfile(self.path) else ...
        self._writer(mode='a', message=["", vm_name, version, "", exit_code])

    def get_total_count(self, column_name: str) -> int:
        return self.report.total_count(self.report.read(self.path), column_name)

    def all_is_passed(self) -> bool:
        df = self.report.read(self.path)
        return df['Exit_code'].eq('Passed').all()
    
    def get_error_vm_list(self) -> list[str]:
        if not isfile(self.path):
            raise FileNotFoundError(f"[red]|ERROR| Report not found: {self.path}")

        df = self.report.read(self.path)
        return df[df['Exit_code'] != 'Passed']['Vm_name'].unique()

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

    @staticmethod
    def _get_version(df):
        if df.empty:
            raise ValueError("Report is empty")

        if not df.loc[0, 'Version']:
            raise ValueError("Version is None")

        if df['Version'].nunique() > 1:
            print("[red]|WARNING| Versions is not unique.")
            return df['Version'].unique()[
                df['Version'].nunique() - 1
            ]

        return df.loc[0, 'Version']

    def send_to_report_portal(self, project_name: str, packege_name: str):
        df = self.report.read(self.path).dropna(how='all')
        version = self._get_version(df)

        if df.empty:
            raise ValueError(f"Report is empty: {self.path}")

        print(f"[green]|INFO| Starting sending to report portal for version: {version}...")
        with PortalManager(project_name=project_name, launch_name=version) as launch:
            self._create_suites(df, launch, packege_name)

            with self.console.status('') as status:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [executor.submit(self._process_row, row, launch, packege_name) for _, row in df.iterrows()]
                    for future in concurrent.futures.as_completed(futures):
                        future.add_done_callback(lambda *_: status.update(self._get_thread_result(future)))

                    concurrent.futures.wait(futures)

    def _process_row(self, row: pd.Series, launch: PortalManager, packege_name: str) -> Optional[str]:
        test = launch.start_test(test_name=row['Test_name'], suite_id=self._create_suite(row, launch, packege_name))

        if not self.is_passed(row):
            test.send_log(message=row['Exit_code'], level='ERROR')

        test.finish(return_code=0 if self.is_passed(row) else 1)

        if not self.is_passed(row):
            self.console.print(
                f"[bold red]|ERROR| [cyan]{row['Test_name']}[/] failed. Exit_Code: {row['Exit_code']}"
            )
            return ''
        return f"[cyan][{'green'}][{row['Os']}] {row['Test_name']} finished with exit code {row['Exit_code']}"

    @staticmethod
    def is_passed(row: pd.Series) -> bool:
        return row['Exit_code'] == 'Passed'

    def _create_suites(self, df: pd.DataFrame, launch: PortalManager, packege_name: str):
        with self.console.status('') as status:
            for _, row in df.iterrows():
                status.update(f"[cyan]|INFO| Created suite {row['Os']} launchers for {row['Version']} test.")
                self._create_suite(row, launch, packege_name)

    @staticmethod
    def _create_suite(row: pd.Series, launch: PortalManager, packege_name: str) -> str:
        return launch.create_suite(row['Os'], parent_suite_id=launch.create_suite(packege_name))

    def exists(self) -> bool:
        return isfile(self.path)

    def send_to_tg(self, data):
        if not isfile(self.path):
            return print(f"[red]|ERROR| Report for sending to telegram not exists: {self.path}")

        update_info = f"{data.update_from} -> " if data.update_from else ""
        result_status = "All tests passed" if self.all_is_passed() else "Some tests have errors"

        caption = (
            f"{data.title} desktop editor tests completed on version: `{update_info}{data.version}`\n\n"
            f"Package: `{self._get_package(data=data)}`\n"
            f"Result: `{result_status}`\n\n"
            f"Number of tested Os: `{self.get_total_count('Exit_code')}`"
        )

        Telegram(token=data.tg_token, chat_id=data.tg_chat_id).send_document(self.path, caption=caption)

    @staticmethod
    def _get_package(data) -> str:
        if data.snap:
            return "Snap Packages"

        if data.appimage:
            return "AppImages"

        if data.flatpak:
            return "FlatPak"

        return "Default Packages"

    def _writer(self, mode: str, message: list, delimiter='\t', encoding='utf-8'):
        self.report.write(self.path, mode, message, delimiter, encoding)

    def _write_titles(self):
        self._writer(mode='w', message=['Os', 'Vm_name', 'Version', 'Package_name', 'Exit_code'])

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
