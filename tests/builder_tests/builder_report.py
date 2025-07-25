# -*- coding: utf-8 -*-
from os import listdir
from os.path import dirname, isfile, join

from host_tools import File
from host_tools.utils import Dir

from frameworks import Report


class BuilderReport:
    titles = ['Builder_samples', 'Test_name', 'Os', 'Version', 'Exit_code', 'Stderr', 'Stdout']
    encoding = 'utf-8'
    delimiter = '\t'

    def __init__(self, report_path: str):
        """
        Initializes the BuilderReport with a specified report path.
        :param report_path: The path where the report will be stored.
        """
        self.base_report = Report()
        self.path = report_path
        self.dir = dirname(self.path)
        Dir.create(self.dir, stdout=False)

    def get_full(self, clear_merged_reports: bool = True) -> str:
        """
        Deletes the existing report file if it exists and merges CSV files from the directory into a single report.
        :return: The path to the merged report.
        """
        self._clear_merged_reports() if clear_merged_reports else None

        self.base_report.merge(
            File.get_paths(self.dir, extension='csv'),
            self.path
        )
        return self.path

    def column_is_empty(self, column_name: str) -> bool:
        """
        Checks if a specified column in the report is empty.
        :param column_name: The name of the column to check.
        :return: True if the column is empty or the file does not exist, otherwise False.
        """
        if not self.base_report.read(self.path)[column_name].count() or not isfile(self.path):
            return True
        return False

    def write(
        self,
        version: str,
        vm_name: str,
        exit_code: str,
        builder_samples: str = 'Not_tested',
        test_name: str = 'Not_tested',
        stderr: str = '',
        stdout: str = ''
    ):
        """
        Writes a new entry to the report with the provided details.
        :param version: The version of the software being tested.
        :param vm_name: The name of the virtual machine used for testing.
        :param exit_code: The exit code of the test.
        :param builder_samples: The builder samples used in the test.
        :param test_name: The name of the test.
        :param stderr: The standard error output from the test.
        :param stdout: The standard output from the test.
        """
        if not isfile(self.path):
            self._write_titles()

        _message = [
            builder_samples,
            test_name,
            vm_name,
            version,
            exit_code,
            stderr,
            stdout
        ]

        self._writer(mode='a', message=_message)

    def exists(self) -> bool:
        """
        Checks if the report file exists.
        :return: True if the report file exists, otherwise False.
        """
        return isfile(self.path)

    def _clear_merged_reports(self) -> None:
        """
        Clears the merged reports.
        """
        File.delete(self.path, stdout=False) if isfile(self.path) else ...
        errors_only_report = self._get_errors_only_report()
        File.delete(errors_only_report, stdout=False) if errors_only_report and isfile(errors_only_report) else ...

    def _get_errors_only_report(self) -> str:
        """
        Returns the path to the errors only report.
        :return: The path to the errors only report.
        """
        for file in listdir(self.dir):
            if file.endswith('_errors_only_report.csv'):
                return join(self.dir, file)
        return None


    def _write_titles(self):
        """
        Writes the header row with column titles to the CSV report.
        """
        self._writer(mode='w', message=self.titles)


    def _writer(self, mode: str, message: list) -> None:
        """
        Writes a message to the report file.
        :param mode: The mode to open the file in.
        :param message: The message to write to the file.
        :param delimiter: The delimiter to use in the file.
        :param encoding: The encoding to use in the file.
        """
        self.base_report.write(
            file_path=self.path,
            mode=mode,
            message=message,
            delimiter=self.delimiter,
            encoding=self.encoding
        )
