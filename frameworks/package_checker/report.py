import csv
from pathlib import Path
from typing import List, Union

from dataclasses import asdict

from frameworks.package_checker.urlcheck_result import URLCheckResult


class CSVReport:
    def __init__(self, path: Union[str, Path], delimiter: str = '\t', encoding='utf-8'):
        self.path = Path(path)
        self.fieldnames = ['version', 'category', 'name', 'url', 'exists', 'status_code', 'error']
        self.delimiter = delimiter
        self.encoding=encoding
        self._ensure_file()

    def _ensure_file(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open('w', newline='', encoding=self.encoding) as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames, delimiter=self.delimiter)
                writer.writeheader()

    def write_results(self, results: List[URLCheckResult]):
        with self.path.open('a', newline='', encoding=self.encoding) as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames, delimiter=self.delimiter)
            for r in results:
                writer.writerow(asdict(r))
