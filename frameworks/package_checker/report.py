import csv
from pathlib import Path
from typing import List, Union, Optional
import pandas as pd


from dataclasses import asdict

from frameworks import Report
from frameworks.package_checker.urlcheck_result import URLCheckResult


class CSVReport(Report):
    def __init__(self, path: Union[str, Path], delimiter: str = '\t', encoding='utf-8'):
        super().__init__()
        self.__df: Optional[pd.DataFrame] = None
        self.__cached_mtime: Optional[float] = None

        self.path = Path(path)
        self.fieldnames = ['version', 'build', 'category', 'name', 'url', 'exists', 'status_code', 'error']
        self.delimiter = delimiter
        self.encoding=encoding
        self.exists_df = self.df if self.exists else None
        self._ensure_file()

    @property
    def df(self) -> Optional[pd.DataFrame]:
        current_mtime = self.path.stat().st_mtime
        if self.__df is None or self.__cached_mtime != current_mtime:
            self.__df = pd.read_csv(self.path, delimiter=self.delimiter)
            self.__cached_mtime = current_mtime

        return self.__df

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    def _ensure_file(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open('w', newline='', encoding=self.encoding) as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames, delimiter=self.delimiter)
                writer.writeheader()

    def write_results(self, results: List[URLCheckResult]):
        existing_df = self.exists_df
        keys = ['version', 'category', 'name', 'url']
        new_rows = [asdict(r) for r in results]

        if existing_df is not None and not existing_df.empty:
            new_df = pd.DataFrame(new_rows)
            merged = new_df.merge(existing_df[keys], on=keys, how='left', indicator=True)
            filtered_rows = new_df[merged['_merge'] == 'left_only']
        else:
            filtered_rows = pd.DataFrame(new_rows)

        if not filtered_rows.empty:
            with self.path.open('a', newline='', encoding=self.encoding) as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames, delimiter=self.delimiter)
                writer.writerows(filtered_rows.to_dict(orient='records'))

    def get_last_exists_version(self, name: str = None, category: str = None) -> Optional[str]:
        if self.df is None or self.df.empty:
            return None

        df = self.df.copy()

        if name:
            df = df[df['name'] == name]

        if category:
            df = df[df['category'] == category]

        if df.empty:
            return None

        return df.loc[df['build'].idxmax()]['version']
    

    @property
    def last_checked_version(self) -> Optional[str]:
        if self.df is None or self.df.empty:
            return None

        df = self.df.copy()
        return df.loc[df['build'].idxmax()]['version']
