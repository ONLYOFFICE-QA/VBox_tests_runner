# -*- coding: utf-8 -*-
import concurrent.futures
from os.path import join, dirname, isfile
from typing import Optional
from rich import print
from rich.console import Console

import pandas as pd
from telegram import Telegram

from frameworks import Report
from frameworks.report_portal import PortalManager


class BuilderReportSender:

    def __init__(self, report_path: str):
        """
        Initialize the BuilderReportSender class.

        :param report_path: Path to the report CSV file.
        """
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
        """
        load and return the DataFrame from the report path.

        :return: The loaded DataFrame or None if not available.
        """
        if self.__df is None and isfile(self.report_path):
            self.__df = self.report.read(self.report_path)
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
            print("[red]|ERROR| Can't read report.csv. Check path: ", self.report_path)
            return None

        if self.df.empty:
            print("[red]|ERROR| Report is empty")
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
        """
        Check if all tests passed (Exit_code == 0.0 and Stderr is empty or NaN).

        :return: True if all tests passed, False otherwise.
        """
        failed_tests = self.df[~((self.df['Exit_code'].eq(0) | self.df['Exit_code'].isna()) &
                                (self.df['Stderr'].isna() | (self.df['Stderr'].notna() & self.df['Stderr'].apply(lambda x: isinstance(x, str) and x.strip() == ''))))]
        print(failed_tests)

        return failed_tests.empty

    def to_telegram(self):
        """
        Send report results to Telegram, including the full and errors-only CSV.
        """
        # Filter rows where Exit_code is not 0 or Stderr is not NaN
        errors_only_df = self.df[(self.df['Exit_code'] != 0) | (self.df['Stderr'].notna())]
        self.report.save_csv(errors_only_df, self.errors_only_report)
        result_status = "All tests passed" if self.all_is_passed() else "Some tests have errors"
        caption = (
            f"Builder tests completed on version: `{self.version}`\n\n"
            f"Result: `{result_status}`"
        )
        self.tg.send_media_group([self.report_path, self.errors_only_report], caption=caption)


    def to_report_portal(self, project_name: str):
        """
        Send test results to the report portal.

        :param project_name: The name of the report portal project.
        """
        self.console.print(f"[green]|INFO| Start sending results to report portal for version: {self.version}...")
        columns_to_check = ['Builder_samples', 'Test_name', 'Os']
        df = self.df.dropna(subset=columns_to_check, how='any')

        if df.empty:
            raise ValueError(f"Report is empty: {self.report_path}")

        with PortalManager(project_name=project_name, launch_name=self.version) as launch:
            self._create_suites(df, launch)

            with self.console.status('') as status:
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
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
        """
        Process a single test row and send it to the report portal.

        :param row: A row from the DataFrame containing test result data.
        :param launch: The PortalManager instance to send results to.
        :return: A status message string or an empty string if the test failed.
        """
        ret_code = self._get_exit_code(row)
        os_suite_uuid = launch.create_suite(row['Os'])
        samples_suite_uuid = launch.create_suite(row['Builder_samples'], parent_suite_uuid=os_suite_uuid)

        log = self._get_log(row)

        launch.set_test_result(
            test_name=row['Test_name'],
            log_message=log,
            return_code=ret_code,
            suite_uuid=samples_suite_uuid
        )

        if ret_code != 0:
            self.console.print(
                f"[bold red]|ERROR| {row['Test_name']} failed. Exit Code: {ret_code}\nConsole log: {log}"
            )
            return ''

        return (
            f"[green]|INFO|[cyan]{row['Os']}[/]|[cyan]{row['Test_name']}[/] "
            f"finished with exit code [cyan]{ret_code}"
        )

    def _create_suites(self, df: pd.DataFrame, launch: PortalManager):
        """
        Create test suites in the report portal based on the DataFrame.

        :param df: The DataFrame containing test results.
        :param launch: The PortalManager instance for suite creation.
        """
        with self.console.status('[cyan]|INFO| Start creating suites') as status:
            for _, row in df.iterrows():
                status.update(
                    f"[cyan]|INFO| Created suite {row['Os']} and {row['Builder_samples']} "
                    f"launchers for {row['Version']} test."
                )

                os_suite_id = launch.create_suite(row['Os'])
                launch.create_suite(row['Builder_samples'], parent_suite_uuid=os_suite_id)

    @staticmethod
    def _get_exit_code(row: pd.Series) -> int:
        """
        Get the exit code from the DataFrame row.

        :param row: A row from the DataFrame.
        :return: The exit code as an integer.
        """
        try:
            ret_code = int(row['Exit_code'])
        except (ValueError, TypeError):
            return 1

        stderr = row.get('Stderr', '')
        if ret_code != 0 or (pd.notna(stderr) and str(stderr).strip()):
            return 1
        return ret_code

    def _get_log(self, row: pd.Series) -> str:
        """
        Generate a log string from Stderr and Stdout if they are not empty.

        :param row: DataFrame row with test results.
        :return: Log string.
        """
        log_parts = []
        for col in ("Stderr", "Stdout"):
            value = row.get(col)
            if pd.notna(value):
                value_str = str(value).strip()
                if value_str:
                    log_parts.append(value_str)
        return "\n".join(log_parts)
