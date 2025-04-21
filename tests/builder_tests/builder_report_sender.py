# -*- coding: utf-8 -*-
import concurrent.futures
from os.path import join, dirname
from typing import Any
from rich import print

import pandas as pd
from telegram import Telegram

from frameworks import Report
from frameworks.report_portal import PortalManager


class BuilderReportSender:

    def __init__(self, report_path: str):
        self.report = Report()
        self.tg = Telegram()
        self.report_path = report_path
        self.df = self.report.read(self.report_path)
        self.version = self._get_version()
        self.errors_only_report = join(dirname(self.report_path), f"{self.version}_errors_only_report.csv")
        self.launch = None

    def _get_version(self):
        if self.df.empty:
            raise ValueError("Report is empty")

        if not self.df.loc[0, 'Version']:
            raise ValueError("Version is None")

        if self.df['Version'].nunique() > 1:
            print("[red]|WARNING| Versions is not unique.")
            return self.df['Version'].unique()[
                self.df['Version'].nunique() - 1
            ]

        return self.df.loc[0, 'Version']

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
            raise ValueError("Report is empty")

        with PortalManager(project_name=project_name, launch_name=self.version) as launch:
            self._create_suites(df, launch)

            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(self._process_row, row, launch) for _, row in df.iterrows()]
                concurrent.futures.wait(futures)


    def _process_row(self, row: pd.Series, launch) -> Any:
        ret_code = self.get_exit_code(row)

        print(
            f"[cyan][{'green' if ret_code == 0 else 'red'}][{row['Os']}] {row['Test_name']} "
            f"finished with exit code {ret_code}"
        )

        os_suite_id = launch.create_suite(row['Os'])
        samples_suite_id = launch.create_suite(row['Builder_samples'], parent_suite_id=os_suite_id)
        test = launch.start_test(test_name=row['Test_name'], suite_id=samples_suite_id)

        if row['ConsoleLog']:
            test.send_log(message=row['ConsoleLog'],level='ERROR' if ret_code != 0 else 'INFO',)

        test.finish(return_code=ret_code)

    @staticmethod
    def _create_suites(df: pd.DataFrame, launch):
        for _, row in df.iterrows():
            print(
                f"[cyan]|INFO| Created suite {row['Os']} and {row['Builder_samples']} "
                f"launchers for {row['Version']} test."
            )

            os_suite_id = launch.create_suite(row['Os'])
            launch.create_suite(row['Builder_samples'], parent_suite_id=os_suite_id)

    @staticmethod
    def get_exit_code(row: pd.Series) -> int:
        try:
            return int(row['Exit_code'])
        except ValueError:
            return row['Exit_code']
