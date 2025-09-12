# -*- coding: utf-8 -*-
from os import listdir
from os.path import join
from typing import Optional, List

from host_tools import File

from tests.common.report_base import BaseReport


class BuilderReport(BaseReport):
    """Builder-specific report implementation"""

    def get_titles(self) -> List[str]:
        """Get column titles for builder report"""
        return ['Builder_samples', 'Test_name', 'Os', 'Version', 'Exit_code', 'Stderr', 'Stdout']


    def write(
        self,
        version: str,
        vm_name: str,
        exit_code: str,
        builder_samples: str = 'Not_tested',
        test_name: str = 'Not_tested',
        stderr: str = '',
        stdout: str = ''
    ) -> None:
        """
        Write new entry to the builder report
        :param version: Software version
        :param vm_name: Virtual machine name
        :param exit_code: Test exit code
        :param builder_samples: Builder samples used
        :param test_name: Test name
        :param stderr: Standard error output
        :param stdout: Standard output
        """
        if not self.exists():
            self._write_titles()

        message = [
            builder_samples,
            test_name,
            vm_name,
            version,
            exit_code,
            stderr,
            stdout
        ]

        self._writer(mode='a', message=message)

    def _clear_merged_reports(self) -> None:
        """Clear merged reports including errors-only reports"""
        super()._clear_merged_reports()
        errors_only_report = self._get_errors_only_report()
        if errors_only_report and File.exists(errors_only_report):
            File.delete(errors_only_report, stdout=False)

    def _get_errors_only_report(self) -> Optional[str]:
        """
        Get path to errors-only report if it exists
        :return: Path to errors-only report or None
        """
        try:
            for file in listdir(self.dir):
                if file.endswith('_errors_only_report.csv'):
                    return join(self.dir, file)
        except (OSError, IOError):
            pass
        return None
