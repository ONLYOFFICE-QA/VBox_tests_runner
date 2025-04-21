# -*- coding: utf-8 -*-
import concurrent.futures
from os.path import join
from typing import Any
from rich import print

import pandas as pd
from telegram import Telegram

from frameworks import Report
from frameworks.report_portal.portal_manager import PortalManager
from tests.builder_tests import BuilderTestData


class BuilderReportSender:

    def __init__(self, report_path: str, test_data: BuilderTestData):
        self.report = Report()
        self.report_path = report_path
        self.test_data = test_data
        self.rp = PortalManager(project_name=self.test_data.portal_project_name)
        self.df = self.report.read(self.report_path)
        self.version = self._get_version()
        self.tg = Telegram()
        self.errors_only_report = join(self.test_data.report.dir, f"{self.version}_errors_only_report.csv")

    def _get_version(self):
        if self.df.empty:
            raise ValueError("Report is empty")

        if not self.df.loc[0, 'Version']:
            raise ValueError("Version is None")

        if self.df['Version'].nunique() > 1:
            print("[red]|WARNING| Version is not unique.")
            return self.df['Version'].unique()[
                self.df['Version'].nunique() - 1
            ]

        return self.df.loc[0, 'Version']

    def to_report_portal(self):
        print(f"[green]|INFO| Starting send to report portal for version: {self.version}...")
        df = self.df.dropna(how='all')

        if df.empty:
            raise ValueError("Report is empty")

        self.rp.start_launcher(launch_name=self.version)
        self._create_suites(df)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self._process_row, row) for _, row in df.iterrows()]
            concurrent.futures.wait(futures)

        self.rp.finish_launcher()

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


    def _process_row(self, row: pd.Series) -> Any:
        ret_code = self.get_exit_code(row)

        print(
            f"[cyan][{'green' if ret_code == 0 else 'red'}][{row['Os']}] {row['Test_name']} "
            f"finished with exit code {ret_code}"
        )

        os_suite_id = self.rp.create_suite(row['Os'])
        samples_suite_id = self.rp.create_suite(row['Builder_samples'], parent_suite_id=os_suite_id)
        self.rp.start_test(test_name=row['Test_name'], suite_id=samples_suite_id)

        if row['ConsoleLog']:
            self.rp.send_test_log(message=row['ConsoleLog'], level='ERROR' if ret_code != 0 else 'WARN')

        self.rp.finish_test(return_code=ret_code, status='PASSED' if ret_code == 0 else 'FAILED')

    def _create_suites(self, df: pd.DataFrame):
        for _, row in df.iterrows():
            print(
                f"[cyan]|INFO| Created suite {row['Os']} and {row['Builder_samples']} "
                f"launchers for {row['Version']} test."
            )

            os_suite_id = self.rp.create_suite(row['Os'])
            self.rp.create_suite(row['Builder_samples'], parent_suite_id=os_suite_id)

    @staticmethod
    def get_exit_code(row: pd.Series) -> int:
        try:
            return int(row['Exit_code'])
        except ValueError:
            return row['Exit_code']
