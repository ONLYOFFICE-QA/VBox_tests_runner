# -*- coding: utf-8 -*-
import concurrent
from rich.console import Console
from frameworks.report_portal import PortalManager
from frameworks.test_data import PortalData
import pandas as pd
from rich import print
from typing import Optional

class BuilderPortalManager():
    """
    Manager for sending test results to Report Portal.

    Handles the process of splitting test results by OS and sending them
    to Report Portal with proper suite organization and concurrent processing.
    """

    def __init__(self, project_name: str, df: pd.DataFrame, version: str):
        self.project_name = project_name
        self.df = df
        self.version = version
        self.console = Console()
        self.portal_data = PortalData()

    def send(self):
        """
        Send test results to Report Portal organized by operating system.

        Splits test results by OS and processes them concurrently,
        creating appropriate suites and sending test results to Report Portal.
        """
        for os_name, df in self.split_by_os().items():
            with PortalManager(
                project_name=self.project_name,
                launch_name=os_name,
                launch_attributes=[{'name': 'Version', 'value': self.version}],
                last_launch_connect=False
            ) as launch:

                self._create_suites(df, launch)
                with self.console.status('') as status:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        futures = [executor.submit(self._process_row, row, launch) for _, row in df.iterrows()]
                        for future in concurrent.futures.as_completed(futures):
                            future.add_done_callback(lambda *_: status.update(self._get_thread_result(future)))

                        concurrent.futures.wait(futures)

    def _process_row(self, row: pd.Series, launch: PortalManager) -> Optional[str]:
        """
        Process a single test row and send it to the report portal.

        :param row: A row from the DataFrame containing test result data.
        :param launch: The PortalManager instance to send results to.
        :return: A status message string or an empty string if the test failed.
        """
        ret_code = self._get_exit_code(row)
        suite_uuid = launch.create_suite(row['Builder_samples'])

        log = self._get_log(row)

        launch.set_test_result(
            test_name=row['Test_name'],
            log_message=log,
            return_code=ret_code,
            suite_uuid=suite_uuid,
            status=self.portal_data.get_status(row['Stdout'])
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

    def _create_suites(self, df: pd.DataFrame, launch: PortalManager):
        """
        Create test suites in the report portal based on the DataFrame.

        :param df: The DataFrame containing test results.
        :param launch: The PortalManager instance for suite creation.
        """
        with self.console.status('[cyan]|INFO| Start creating suites') as status:
            for _, row in df.iterrows():
                status.update(
                    f"[cyan]|INFO| Created suite {row['Builder_samples']} "
                    f"launchers for {row['Version']} test."
                )
                launch.create_suite(row['Builder_samples'])

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


    def split_by_os(self) -> dict[str, pd.DataFrame]:
        """
        Split the DataFrame into multiple DataFrames by unique OS values.

        :return: Dictionary where keys are OS names and values are DataFrames for each OS
        """
        if 'Os' not in self.df.columns:
            print("[red]|ERROR| Column 'Os' not found in report")
            return {}

        unique_os = self.df['Os'].dropna().unique()

        if len(unique_os) == 0:
            print("[yellow]|WARNING| No valid OS values found in report")
            return {}

        os_dataframes = {}
        for os_name in unique_os:
            os_df = self.df[self.df['Os'] == os_name].copy()
            if not os_df.empty:
                os_dataframes[os_name] = os_df
                print(f"[green]|INFO| Created DataFrame for OS '{os_name}' with {len(os_df)} rows")

        print(f"[cyan]|INFO| Successfully split report into {len(os_dataframes)} OS-specific DataFrames")
        return os_dataframes


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
                value_str = f"{col}: {value}".strip()
                if value_str:
                    log_parts.append(value_str)
        return "\n".join(log_parts)
