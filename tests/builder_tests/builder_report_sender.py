# -*- coding: utf-8 -*-
import concurrent.futures
from os.path import join, dirname, isfile
from typing import Any, Optional
from rich import print
from rich.console import Console

import pandas as pd
from telegram import Telegram

from frameworks import Report
from frameworks.report_portal import PortalManager


class BuilderReportSender:

    def __init__(self, report_path: str):
        self.report = Report()
        self.tg = Telegram()
        self.report_path = report_path
        self.__df = None
        self.__version = None
        self.errors_only_report = join(dirname(self.report_path), f"{self.version}_errors_only_report.csv")
        self.console = Console()
        self.launch = None

    @property
    def df(self):
        if self.__df is None and isfile(self.report_path):
            self.__df = self.report.read(self.report_path)
        return self.__df

    @property
    def version(self):
        if not self.df or self.df.empty:
            return None

        if not self.df.loc[0, 'Version']:
            raise ValueError("Version is None")

        if self.df['Version'].nunique() > 1:
            print("[red]|WARNING| Versions is not unique.")
            self.__version = self.df['Version'].unique()[
                self.df['Version'].nunique() - 1
            ]
        else:
            self.__version = self.df.loc[0, 'Version']

        return self.__version

    def all_is_passed(self) -> bool:
        return self.df['Exit_code'].eq(0.0).all()

    def to_telegram(self):
        errors_only_df = self.df[self.df['Exit_code'] != 0.0]
        self.report.save_csv(errors_only_df, self.errors_only_report)
        result_status = "All tests passed" if self.all_is_passed() else "Some tests have errors"
        caption = (
            f"Builder tests completed on version: `{self.version}`\n\n"
            f"Result: `{result_status}`"
        )
        self.tg.send_media_group([self.report_path, self.errors_only_report], caption=caption)


    def to_report_portal(self, project_name: str):
        print(f"[green]|INFO| Starting sending to report portal for version: {self.version}...")
        df = self.df.dropna(how='all')

        if df.empty:
            raise ValueError(f"Report is empty: {self.report_path}")

        with PortalManager(project_name=project_name, launch_name=self.version) as launch:
            self._create_suites(df, launch)

            with self.console.status('') as status:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [executor.submit(self._process_row, row, launch) for _, row in df.iterrows()]
                    for future in concurrent.futures.as_completed(futures):
                        future.add_done_callback(lambda *_: status.update(self._get_thread_result(future)))

                    concurrent.futures.wait(futures)

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

    def _process_row(self, row: pd.Series, launch: PortalManager) -> Optional[str]:
        ret_code = self._get_exit_code(row)
        os_suite_id = launch.create_suite(row['Os'])
        samples_suite_id = launch.create_suite(row['Builder_samples'], parent_suite_id=os_suite_id)
        test = launch.start_test(test_name=row['Test_name'], suite_id=samples_suite_id)

        if row['ConsoleLog']:
            test.send_log(message=row['ConsoleLog'], level='ERROR' if ret_code != 0 else 'INFO')

        test.finish(return_code=ret_code)

        if ret_code != 0:
            self.console.print(
                f"[bold red]|ERROR| {row['Test_name']} failed. Exit Code: {ret_code}\nConsole log: {row['ConsoleLog']}"
            )
            return ''

        return f"[cyan]|INFO|[{'green'}][{row['Os']}] {row['Test_name']} finished with exit code {ret_code}"

    def _create_suites(self, df: pd.DataFrame, launch: PortalManager):
        with self.console.status('') as status:
            for _, row in df.iterrows():
                status.update(
                    f"[cyan]|INFO| Created suite {row['Os']} and {row['Builder_samples']} "
                    f"launchers for {row['Version']} test."
                )
                os_suite_id = launch.create_suite(row['Os'])
                launch.create_suite(row['Builder_samples'], parent_suite_id=os_suite_id)

    @staticmethod
    def _get_exit_code(row: pd.Series) -> int:
        try:
            return int(row['Exit_code'])
        except ValueError:
            return row['Exit_code']
