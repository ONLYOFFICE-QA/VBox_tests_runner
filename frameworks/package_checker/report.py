import csv
from pathlib import Path
from typing import List, Union, Optional
import pandas as pd

from dataclasses import asdict
from frameworks import Report

from .urlcheck_result import URLCheckResult


class CSVReport(Report):
    """A class for handling CSV report generation and management for URL check results.

    :param path: Path to the CSV file
    :param delimiter: Delimiter to use in the CSV file
    :param encoding: File encoding to use
    """
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
        """Get the DataFrame containing the report data.

        :return: DataFrame with report data or None if file doesn't exist
        """
        current_mtime = self.path.stat().st_mtime
        if self.__df is None or self.__cached_mtime != current_mtime:
            self.__df = pd.read_csv(self.path, delimiter=self.delimiter)
            self.__cached_mtime = current_mtime

        return self.__df

    
    def update_df(self):
        """Update the DataFrame with the latest data from the report file.

        :return: DataFrame with report data or None if file doesn't exist
        """
        self.__df = pd.read_csv(self.path, delimiter=self.delimiter)

    @property
    def exists(self) -> bool:
        """Check if the report file exists.

        :return: True if file exists, False otherwise
        """
        return self.path.is_file()

    def _ensure_file(self):
        """Ensure the report file and its parent directories exist.
        Creates the file with headers if it doesn't exist.

        :raises OSError: If file/directory creation fails
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open('w', newline='', encoding=self.encoding) as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames, delimiter=self.delimiter)
                writer.writeheader()

    def write_results(self, results: List[URLCheckResult]):
        """Write URL check results to the report file.

        :param results: List of URLCheckResult objects to write
        :raises OSError: If file writing fails
        """
        existing_df = self.exists_df
        keys = ['version', 'category', 'name']
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

    def get_last_exists_version(self, name: Optional[str] = None, category: Optional[str] = None) -> Optional[str]:
        """Get the latest version where the package exists in the report.

        :param name: Name of the package to check
        :param category: Category of the package to check
        :return: Latest version string or None if not found
        """
        if self.df is None or self.df.empty:
            return None

        df = self.df.copy()

        if name:
            df = df[df['name'] == name.lower()]

        if category:
            df = df[df['category'] == category.lower()]

        df = df[df['exists'].astype(bool)]

        if df.empty:
            return None

        return df.loc[df['build'].idxmax()]['version']

    def get_result(self, version: str, name: str, category: str) -> Optional[bool]:
        """
        Get the results for a given version, name and category.

        :param version: Version to check
        :param name: Name of the package to check
        :param category: Category of the package to check
        :return: Boolean value from exists column or None if not found
        """
        if self.df is None or self.df.empty:
            return None

        df = self.df.copy()
        df = df[df['version'] == str(version)]

        if name:
            df = df[df['name'] == name.lower()]

        if category:
            df = df[df['category'] == category.lower()]

        return bool(df['exists'].iloc[0]) if not df.empty else None


    @property
    def last_checked_version(self) -> Optional[str]:
        """Get the latest version where the package exists in the report.

        :param None: No parameters
        :return: Latest version string or None if not found
        """
        if self.df is None or self.df.empty:
            return None

        df = self.df.copy()
        return df.loc[df['build'].idxmax()]['version']
