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
        self.keys = ['version', 'build', 'category', 'name']
        self.delimiter = delimiter
        self.encoding = encoding
        self._ensure_file()

    @property
    def df(self) -> Optional[pd.DataFrame]:
        """Get the DataFrame containing the report data.

        :return: DataFrame with report data or None if file doesn't exist
        """
        current_mtime = self.path.stat().st_mtime
        if self.__df is None or self.__cached_mtime != current_mtime:
            self.update_df()
            self.__cached_mtime = current_mtime

        return self.__df

    def update_df(self):
        """Update the DataFrame with the latest data from the report file.

        :return: DataFrame with report data or None if file doesn't exist
        """
        try:
            # Read CSV with explicit column names to handle cases where column order might be inconsistent
            self.__df = pd.read_csv(
                self.path,
                delimiter=self.delimiter,
                names=self.fieldnames,
                header=0,
                encoding=self.encoding
            )
        except Exception as _:
            # Fallback to regular read if there are issues
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
        # Get fresh data from file instead of cached property
        existing_df = self.df if self.exists else None
        new_rows = [asdict(r) for r in results]

        if existing_df is not None and not existing_df.empty:
            new_df = pd.DataFrame(new_rows)
            merged = new_df.merge(existing_df[self.keys], on=self.keys, how='left', indicator=True)
            mask = merged['_merge'] == 'left_only'
            filtered_rows = new_df.loc[mask]
        else:
            filtered_rows = pd.DataFrame(new_rows)

        if not filtered_rows.empty:
            with self.path.open('a', newline='', encoding=self.encoding) as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames, delimiter=self.delimiter)
                writer.writerows(filtered_rows.to_dict(orient='records'))

            # Invalidate cache after writing to ensure fresh data on next read
            self.__df = None
            self.__cached_mtime = None

    def update_results(self, results: List[URLCheckResult]):
        """Update existing URL check results in the report file.

        :param results: List of URLCheckResult objects to update
        :raises OSError: If file operations fail
        """
        if not self.exists or not results:
            return

        existing_df = self.df.copy()
        new_results_df = pd.DataFrame([asdict(r) for r in results])
        updated_df = existing_df.set_index(self.keys).sort_index()
        new_df = new_results_df.set_index(self.keys).sort_index()

        updated_df.update(new_df)

        final_df = updated_df.reset_index()
        final_df = final_df[self.fieldnames]
        final_df.to_csv(self.path, sep=self.delimiter, index=False, encoding=self.encoding)

        self.__df = None
        self.__cached_mtime = None

    def get_last_exists_version(self, name: Optional[str] = None, category: Optional[str] = None, any_exists: bool = True) -> Optional[str]:
        """Get the latest version where packages of the category exist in the report.

        :param name: Name of the package to check
        :param category: Category of the package to check
        :param any_exists: If True, find version where at least one package exists. If False, find version where all packages exist
        :return: Latest version string or None if not found
        """
        if self.df is None or self.df.empty:
            return None

        df = self.df.copy()

        filter_conditions = []

        if name:
            filter_conditions.append(f"name == '{name.lower()}'")
        if category:
            filter_conditions.append(f"category == '{category.lower()}'")

        if filter_conditions:
            df = df.query(' and '.join(filter_conditions)).copy()

        if df.empty:
            return None

        df['build'] = pd.to_numeric(df['build'], errors='coerce')
        df['exists'] = df['exists'].astype(bool)

        version_stats = df.groupby('version').agg({
            'exists': 'any' if any_exists else 'all',
            'build': 'first'
        })

        valid_versions = version_stats[
            version_stats['exists'] &
            version_stats['build'].notna()
        ]

        if valid_versions.empty:
            return None

        return valid_versions['build'].idxmax()


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

    def get_latest_versions(self, count: int = 2) -> List[str]:
        """
        Get the latest N versions from the report based on build numbers.

        :param count: Number of latest versions to return
        :return: List of version strings ordered by build number (latest first)
        """
        if self.df is None or self.df.empty:
            return []

        df = self.df.copy()

        # Ensure build column is numeric
        df['build'] = pd.to_numeric(df['build'], errors='coerce')

        # Remove rows where build conversion failed
        df = df.dropna(subset=['build'])

        if df.empty:
            return []

        # Get unique versions with their maximum build numbers
        version_builds = df.groupby('version')['build'].max().reset_index()

        # Sort by build number in descending order
        version_builds = version_builds.sort_values('build', ascending=False)

        # Return the top N versions
        return version_builds.head(count)['version'].tolist()

    def version_exists(self, version: str) -> bool:
        """
        Check if version exists in report.

        :param version: Version to check.
        :return: True if version exists in report, False otherwise.
        """
        df = self.df

        if df is not None and not df.empty:
            return str(version) in df['version'].values
        return False

    def get_existing_versions(self) -> set[str]:
        """
        Get all existing versions from report.
        """
        df = self.df
        if df is not None and not df.empty:
            return set(df['version'].unique())
        return set()

    @property
    def last_checked_version(self) -> Optional[str]:
        """Get the latest version where the package exists in the report.

        :param None: No parameters
        :return: Latest version string or None if not found
        """
        if self.df is None or self.df.empty:
            return None

        df = self.df.copy()
        df['build'] = pd.to_numeric(df['build'], errors='coerce')
        return df.loc[df['build'].idxmax()]['version']
