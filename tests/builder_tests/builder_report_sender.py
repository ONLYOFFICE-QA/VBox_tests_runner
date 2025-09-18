# -*- coding: utf-8 -*-
import concurrent.futures
from os.path import join, dirname, isfile, expanduser
from typing import Optional
from rich.console import Console
from host_tools import File, HostInfo
import pandas as pd
from telegram import Telegram

from frameworks import Report
from frameworks.test_data import PortalData
from tests.builder_tests.builder_test_data import BuilderTestData
from .report_portal_manager import ReportPortalManager


class BuilderReportSender:

    def __init__(self, test_data: BuilderTestData):
        """
        Initialize the BuilderReportSender class.

        :param report_path: Path to the report CSV file.
        """
        self.data = test_data
        self.portal_data = PortalData()
        self.console = Console()
        self.report = Report()
        self.tg = Telegram(token=self._get_token(self.data.token_file), chat_id=self._get_chat_id(test_data.chat_id_file))
        self.report_path = self.data.report.path
        self.__df = None
        self.__version = None
        self.errors_only_report = join(dirname(self.report_path), f"{self.version}_errors_only_report.csv")

    def _get_token(self, token_file_name: str) -> str:
        """
        Get the token from the token file.
        """
        return File.read(join(expanduser('~'), '.telegram', token_file_name or 'token')).strip()

    def _get_chat_id(self, chat_id_file_name: str) -> str:
        """
        Get the chat id from the chat id file.
        """
        return File.read(join(expanduser('~'), '.telegram', chat_id_file_name or 'chat')).strip()


    @property
    def df(self):
        """
        Load and return the DataFrame from the report path.

        :return: The loaded DataFrame or None if not available.
        """
        if self.__df is None:
            if isfile(self.report_path):
                self.__df = self.report.read(self.report_path)
            else:
                self.console.print("[red]|ERROR| Can't read report.csv. Check path: ", self.report_path)
        return self.__df

    @property
    def version(self):
        """
        Determine and return the version from the report DataFrame.

        :return: The version string or None if not found.
        """
        if self.__version is not None:
            return self.__version

        if self.df is None:
            return None

        if self.df.empty:
            self.console.print("[red]|ERROR| Report is empty")
            return None

        if not self.df.loc[0, 'Version']:
            raise ValueError("Version is None")

        if self.df['Version'].nunique() > 1:
            self.console.print("[red]|WARNING| Versions is not unique.")
            self.__version = self.df['Version'].unique()[
                self.df['Version'].nunique() - 1
            ]
        else:
            self.__version = self.df.loc[0, 'Version']

        return self.__version

    def get_errors_only_df(self) -> Optional[pd.DataFrame]:
        """
        Get DataFrame with only failed tests (Exit_code != 0 or Stderr is not empty).

        :return: DataFrame with failed tests or None if no data
        """
        df = self.df
        if df is None or df.empty:
            return None

        failed = df[
            (df['Exit_code'].fillna(0) != 0) |
            (df['Stderr'].notna() & df['Stderr'].astype(str).str.strip().ne(''))
            ]
        return failed

    def to_telegram(self) -> None:
        """
        Send report results to Telegram, including the full and errors-only CSV.
        """
        errors_only_df = self.get_errors_only_df()

        if errors_only_df is not None:
            self.report.save_csv(errors_only_df, self.errors_only_report)

        self.tg.send_media_group([self.report_path, self.errors_only_report], caption=self.get_caption(errors_only_df))

    def _get_os_list_by_status(self, status: str):
        df = self.df.copy()
        filtered_df = df[df['Stdout'] == status]
        return list(filtered_df['Os'].unique()) if not filtered_df.empty else []

    def get_caption(self, errors_only_df: pd.DataFrame) -> str:
        """
        Get caption for Telegram message.

        :return: Caption string
        """
        total_tests = len(self.df) if self.df is not None and not self.df.empty else 0
        package_not_exists_os = self._get_os_list_by_status(self.portal_data.test_status.not_exists_package)
        failed_create_vm_os = self._get_os_list_by_status(self.portal_data.test_status.failed_create_vm)

        result_status = "All tests passed" if errors_only_df is None or errors_only_df.empty else "Some tests have errors"
        caption_parts = [
            f"Builder tests completed on version: `{self.version}`\n\n",
            f"Runned on: `{HostInfo().os}`\n",
            f"Result: `{result_status}`\n\n",
        ]

        if package_not_exists_os:
            caption_parts.append(f"Package not exists for OS: `{', '.join(package_not_exists_os)}`\n\n")

        if failed_create_vm_os:
            caption_parts.append(f"Failed to create VM for OS: `{', '.join(failed_create_vm_os)}`\n\n")

        caption_parts.append(f"Total tests: `{total_tests}`")

        return ''.join(caption_parts)

    def to_report_portal(self, project_name: str) -> None:
        """
        Send test results to the report portal.

        :param project_name: The name of the report portal project.
        """
        self.console.print(f"[green]|INFO| Start sending results to report portal for version: {self.version}...")
        columns_to_check = ['Builder_samples', 'Test_name', 'Os']
        df = self.df.dropna(subset=columns_to_check, how='any')

        if df.empty:
            raise ValueError(f"Report is empty: {self.report_path}")

        ReportPortalManager(project_name=project_name, df=df, version=self.version).send()
