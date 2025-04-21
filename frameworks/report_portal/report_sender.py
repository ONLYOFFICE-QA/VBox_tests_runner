# -*- coding: utf-8 -*-
import asyncio
import concurrent.futures
from typing import Any

import pandas as pd

from frameworks import Report
from frameworks.report_portal.portal_manager import PortalManager


class ReportSender:


    def __init__(self, report_path: str):
        self.report = Report()
        self.report_path = report_path
        self.project_name = 'nikolai_personal'
        self.rp = PortalManager(project_name=self.project_name)

    def handel_report(self):
        df = self.report.read(self.report_path)

        for _, row in df.iterrows():
            self._process_row(row)

        self.rp.finish_launcher()

    def _process_row(self, row: pd.Series) -> Any:
        ret_code = self.get_exit_code(row)
        log = row['ConsoleLog']
        self.rp.start_launcher(launch_name=row['Version'])
        print(f"[{row['Os']}] {row['Test_name']} finished with exit code {ret_code}")
        os_suite_id = self.rp.create_suite(row['Os'])
        samples_suite_id = self.rp.create_suite(row['Builder_samples'], parent_suite_id=os_suite_id)
        self.rp.start_test(test_name=row['Test_name'], suite_id=samples_suite_id)

        if log:
            self.rp.send_test_log(message=log, level='ERROR' if ret_code != 0 else 'WARN')

        self.rp.finish_test(return_code=ret_code)

    @staticmethod
    def get_exit_code(row: pd.Series) -> int:
        try:
            return int(row['Exit_code'])
        except ValueError:
            return row['Exit_code']
