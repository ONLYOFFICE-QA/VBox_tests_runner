# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Union
import csv
from frameworks.report import Report


class TestsRunnerReport(Report):

    def __init__(self, path: Union[str, Path], delimiter: str = '\t', encoding='utf-8'):
        super().__init__()
        self.path = Path(path)
        self.delimiter = delimiter
        self.encoding = encoding
        self.fieldnames = ['version', 'build', 'category', 'name', 'result']
        self._ensure_file()

    def _ensure_file(self):
        """
        Ensure the report file and its parent directories exist.
        Creates the file with headers if it doesn't exist.

        :raises OSError: If file/directory creation fails
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open('w', newline='', encoding=self.encoding) as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames, delimiter=self.delimiter)
                writer.writeheader()
