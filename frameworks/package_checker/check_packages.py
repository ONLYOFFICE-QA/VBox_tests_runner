# -*- coding: utf-8 -*-
from os.path import join
from typing import Dict, List, Union, Optional
import asyncio
import logging
from contextlib import asynccontextmanager, nullcontext

import aiohttp
from aiohttp import ClientSession, ClientTimeout, ClientConnectorError
from host_tools import HostInfo
from rich import print

from .config import Config
from .report import CSVReport
from ..VersionHandler import VersionHandler

from .urlcheck_params import URLCheckParams
from .urlcheck_result import URLCheckResult



class PackageURLChecker:
    """Async URL checker for package versions with improved error handling and performance."""
    __cached_reports = {}
    __cached_versions = {}

    def __init__(
            self,
            max_concurrent: int = None,
            timeout: int = 10,
            max_retries: int = 2
    ):
        """
        Initialize the URL checker with concurrency and timeout settings.

        :param max_concurrent: Maximum number of concurrent requests.
        :param timeout: Request timeout in seconds.
        :param max_retries: Number of retries for failed requests.
        """
        self.config = Config()

        # Performance and reliability settings
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent else nullcontext()

        # Setup logging
        self.logger = logging.getLogger(__name__)

    def get_report(self, base_version: str) -> CSVReport:
        """
        Get or create a cached CSVReport object for the given version.

        :param base_version: The base version string.
        :return: CSVReport object for that version.
        """
        report_path = join(self.config.report_dir, f'{base_version}.csv')
        if report_path not in self.__cached_reports:
            self.__cached_reports[report_path] = CSVReport(path=report_path)
        return self.__cached_reports[report_path]

    def run(
            self,
            versions: Union[str, VersionHandler, List[Union[str, VersionHandler]]],
            categories: Optional[List[str]] = None,
            names: Optional[List[str]] = None,
            stdout: bool = True
    ) -> Dict[str, Dict[str, Dict[str, Dict[str, object]]]]:
        """
        Run URL checks and optionally print the results.

        :param versions: One or more version strings or VersionHandler objects.
        :param categories: Optional list of categories to filter.
        :param names: Optional list of names to filter.
        :param stdout: Whether to print results to console.
        :return: Nested dictionary of results.
        """
        try:
            results = asyncio.run(self.check_urls(versions=versions, categories=categories, names=names))
            grouped = self._build_grouped_results(results)

            if stdout:
                self._print_results(grouped)
                self._print_summary(results)

            return grouped
        except Exception as e:
            self.logger.error(f"Error during URL checking: {e}")
            raise

    def recheck_versions(
            self,
            base_version: str,
            count: Optional[int] = 2,
            recheck_all: bool = False,
            categories: Optional[List[str]] = None,
            names: Optional[List[str]] = None,
            stdout: bool = True
    ) -> None:
        """
        Recheck existing versions in the report and update their status.

        :param base_version: The base version string (x.x.x).
        :param count: Number of latest versions to recheck (None for 2).
        :param recheck_all: If True, recheck all versions in report.
        :param categories: Optional list of categories to check.
        :param names: Optional list of names to check.
        :param stdout: Whether to print results to console.
        """
        asyncio.run(self._recheck_latest_versions(
            report=self.get_report(base_version=base_version),
            categories=categories,
            names=names,
            stdout=stdout,
            recheck_count=count,
            recheck_all=recheck_all
        ))

    def check_versions(
            self,
            base_version: str,
            max_builds: int = 200,
            stdout: bool = True,
            recheck_count: Optional[int] = 2,
            recheck_all: bool = False
    ) -> None:
        """
        Check versions and update the report.

        :param base_version: The base version string (x.x.x).
        :param max_builds: Maximum number of builds to check upwards.
        :param stdout: Whether to print results to console.
        :param recheck_count: Number of latest versions to recheck (None to skip recheck).
        :param recheck_all: If True, recheck all versions in report (overrides recheck_count).
        """
        asyncio.run(self.find_latest_valid_version(
            base_version=base_version,
            max_builds=max_builds,
            stdout=stdout,
            recheck_count=recheck_count,
            recheck_all=recheck_all
        ))

    async def find_latest_valid_version(
            self,
            base_version: str,
            max_builds: int = 200,
            categories: Optional[List[str]] = None,
            names: Optional[List[str]] = None,
            stdout: bool = True,
            recheck_count: Optional[int] = 2,
            recheck_all: bool = False
    ) -> Optional[str]:
        """
        Find the most recent version with all required URLs present.

        :param base_version: Base version string to start from (x.x.x).
        :param max_builds: Maximum number of builds to check upwards.
        :param categories: Optional list of categories to check.
        :param names: Optional list of names to check.
        :param stdout: Whether to print results to console.
        :param recheck_count: Number of latest versions to recheck (None to skip recheck).
        :param recheck_all: If True, recheck all versions in report (overrides recheck_count).
        :return: The latest valid version string or None.
        """

        report = self.get_report(base_version=base_version)

        if recheck_all or recheck_count:
            await self._recheck_latest_versions(
                report=report,
                categories=categories,
                names=names,
                stdout=stdout,
                recheck_count=recheck_count,
                recheck_all=recheck_all
            )

        existing_versions = report.get_existing_versions()
        last_version = report.last_checked_version
        start_build = self._get_version(last_version).build if last_version else 0
        end_build = start_build + max_builds

        versions = []
        for build in range(start_build + 1, end_build + 1):
            version_str = f"{base_version}.{build}"
            if version_str not in existing_versions:
                versions.append(self._get_version(version=version_str))

        async def check_version(v: VersionHandler) -> Optional[str]:
            results = await self.check_urls(versions=[v], categories=categories, names=names)

            if all(r.exists is True for r in results):
                if stdout:
                    print(f"[green]✅ All packages found in version {v}[/green]")
                return str(v)
            else:
                if stdout:
                    print(f"[dim]❌ Not all packages found in version {v}[/dim]")
                return None

        tasks = [check_version(v) for v in versions]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        valid_versions = [result for result in results if result is not None]

        if valid_versions:
            latest_version = max(valid_versions, key=lambda x: self._get_version(x).build)
            return latest_version

        return None

    def _get_version(self, version: str) -> VersionHandler:
        """
        Get or cache a VersionHandler instance.

        :param version: Version string.
        :return: VersionHandler instance.
        """
        if version not in self.__cached_versions:
            self.__cached_versions[version] = VersionHandler(version)
        return self.__cached_versions[version]

    def _get_versions(
            self,
            versions: Union[str, VersionHandler, List[Union[str, VersionHandler]]]
    ) -> List[VersionHandler]:
        """
        Normalize input into a list of VersionHandler instances.

        :param versions: One or more versions (str or VersionHandler).
        :return: List of VersionHandler objects.
        """
        if not isinstance(versions, list):
            versions = [versions if isinstance(versions, VersionHandler) else self._get_version(version=versions)]
        return [v if isinstance(v, VersionHandler) else self._get_version(version=v) for v in versions]

    def generate_urls(
            self,
            version: VersionHandler,
            categories: Optional[List[str]] = None,
            names: Optional[List[str]] = None
    ) -> List[URLCheckParams]:
        """
        Generate URL parameters for the given version.

        :param version: VersionHandler instance.
        :param categories: Optional list of categories to include.
        :param names: Optional list of names to include.
        :return: List of URLCheckParams.
        """
        params_list = []

        for category, templates in self.config.templates.items():
            if categories and category not in categories:
                continue

            for name, tpl in templates.items():
                if names and name not in names:
                    continue

                try:
                    url = tpl.format(
                        host=self.config.host,
                        version=version.without_build,
                        build=version.build,
                        **({"branch": self.get_branch(version)} if "{branch}" in tpl else {})
                    )
                    params_list.append(URLCheckParams(
                        version=str(version),
                        build=version.build,
                        category=category,
                        name=name,
                        url=url
                    ))
                except KeyError as e:
                    self.logger.warning(f"Template formatting error for {category}.{name}: {e}")
                    continue

        return params_list

    def get_branch(self, version: VersionHandler) -> str:
        """
        Get the branch name for the given version.

        :param version: VersionHandler instance.
        :return: Branch name.
        """
        if version.minor == 0:
            return "release"
        elif '99.99.99' in str(version):
            return "develop"
        return "hotfix"

    async def _recheck_latest_versions(
            self,
            report,
            categories: Optional[List[str]] = None,
            names: Optional[List[str]] = None,
            stdout: bool = True,
            recheck_count: Optional[int] = 2,
            recheck_all: bool = False
    ) -> None:
        """
        Recheck and update status of versions in the report.

        :param report: CSVReport instance to check and update
        :param categories: Optional list of categories to check
        :param names: Optional list of names to check
        :param stdout: Whether to print results to console
        :param recheck_count: Number of latest versions to recheck
        :param recheck_all: If True, recheck all versions in report
        """
        if recheck_all:
            # Get all unique versions from the report
            if report.df is None or report.df.empty:
                return
            latest_versions = report.df['version'].unique().tolist()
            if stdout:
                print(f"[blue]Rechecking ALL {len(latest_versions)} versions in report[/blue]")
        else:
            latest_versions = report.get_latest_versions(count=recheck_count or 1)
            if stdout:
                print(f"[blue]Rechecking latest {len(latest_versions)} versions: {latest_versions}[/blue]")
        if not latest_versions:
            return

        updated_results = []

        async with self._get_session() as session:
            for version_str in latest_versions:
                version = self._get_version(version_str)
                params_list = self.generate_urls(version, categories=categories, names=names)

                # Check current status of packages for this version
                version_tasks = [self._check_url_with_retry(session, param) for param in params_list]
                current_results = await asyncio.gather(*version_tasks, return_exceptions=False)

                # Check if any statuses have changed
                has_changes = False
                for result in current_results:
                    old_result = report.get_result(version=result.version, name=result.name, category=result.category)
                    if old_result != result.exists:
                        has_changes = True
                        if stdout:
                            status_change = f"{'❌→✅' if result.exists else '✅→❌'}"
                            print(f"[yellow]{status_change} {result.category}.{result.name} in {result.version}[/yellow]")

                if has_changes:
                    updated_results.extend(current_results)
                    if stdout:
                        print(f"[green]Updated status for version {version_str}[/green]")

        if updated_results:
            report.update_results(updated_results)
            if stdout:
                print(f"[green]Report updated with {len(updated_results)} package status changes[/green]")

    @asynccontextmanager
    async def _get_session(self):
        """
        Async context manager for aiohttp session with custom settings.

        :return: AIOHTTP ClientSession.
        """
        timeout = ClientTimeout(total=self.timeout, connect=5)
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=20,  # Max connections per host
            keepalive_timeout=30,
            enable_cleanup_closed=True,
            ssl=False if HostInfo().is_mac else True
        )

        async with ClientSession(timeout=timeout, connector=connector) as session:
            yield session

    async def check_urls(
            self,
            versions: Union[str, VersionHandler, List[Union[str, VersionHandler]]],
            categories: Optional[List[str]] = None,
            names: Optional[List[str]] = None
    ) -> List[URLCheckResult]:
        """
        Check multiple URLs for multiple versions.

        :param versions: One or more versions to check.
        :param categories: Optional category filter.
        :param names: Optional name filter.
        :return: List of URLCheckResult instances.
        """
        all_results = []

        async with self._get_session() as session:
            for version in self._get_versions(versions):
                report = self.get_report(base_version=version.without_build)
                params_list = self.generate_urls(version, categories=categories, names=names)
                version_tasks = [self._check_url_with_retry(session, param) for param in params_list]

                if len(version_tasks) > 100:
                    version_results = await self._check_urls_with_progress(version_tasks)
                else:
                    version_results = await asyncio.gather(*version_tasks, return_exceptions=False)

                if any(r.exists is True for r in version_results) and not report.version_exists(version):
                    report.write_results(version_results)

                all_results.extend(version_results)

        return all_results

    @staticmethod
    async def _check_urls_with_progress(tasks: List) -> List[URLCheckResult]:
        """
        Execute tasks with progress indication in batches.

        :param tasks: List of coroutines to execute.
        :return: List of URLCheckResult instances.
        """
        results = []
        batch_size = 50
        total_batches = (len(tasks) + batch_size - 1) // batch_size

        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=False)
            results.extend(batch_results)

            current_batch = (i // batch_size) + 1
            print(f"[dim]Progress: {current_batch}/{total_batches} batches completed[/dim]")

        return results

    async def _check_url_with_retry(self, session: ClientSession, param: URLCheckParams) -> URLCheckResult:
        """
        Attempt to check a URL with retries.

        :param session: Active aiohttp session.
        :param param: URLCheckParams instance.
        :return: URLCheckResult instance.
        """
        async with self.semaphore:
            for attempt in range(self.max_retries + 1):
                try:
                    result = await self._check_url(session, param)
                    if result.exists is not None:  # Success or definitive failure
                        return result
                except Exception as e:
                    if attempt == self.max_retries:
                        self.logger.error(f"Failed to check {param.url} after {self.max_retries + 1} attempts: {e}")
                        return URLCheckResult(**param.__dict__, exists=None, error=str(e))
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff

        return URLCheckResult(**param.__dict__, exists=None, error="Max retries exceeded")

    async def _check_url(self, session: ClientSession, param: URLCheckParams) -> URLCheckResult:
        """
        Perform a single HTTP HEAD request to the URL.

        :param session: AIOHTTP ClientSession.
        :param param: URLCheckParams instance.
        :return: URLCheckResult instance.
        """
        try:
            async with session.head(param.url) as response:
                exists = response.status == 200
                return URLCheckResult(
                    **param.__dict__,
                    exists=exists,
                    status_code=response.status
                )
        except ClientConnectorError as e:
            self.logger.debug(f"Connection error for {param.url}: {e}")
            return URLCheckResult(**param.__dict__, exists=False, error="Connection failed")
        except asyncio.TimeoutError:
            self.logger.debug(f"Timeout for {param.url}")
            return URLCheckResult(**param.__dict__, exists=None, error="Timeout")
        except Exception as e:
            self.logger.debug(f"Unexpected error for {param.url}: {e}")
            return URLCheckResult(**param.__dict__, exists=None, error=str(e))

    @staticmethod
    def _build_grouped_results(results: List[URLCheckResult]) -> Dict[str, Dict[str, Dict[str, Dict[str, object]]]]:
        """
        Convert flat list of results into grouped nested structure.

        :param results: List of URLCheckResult objects.
        :return: Nested dictionary of grouped results.
        """
        grouped: Dict[str, Dict[str, Dict[str, Dict[str, object]]]] = {}

        for result in results:
            version_dict = grouped.setdefault(result.version, {})
            category_dict = version_dict.setdefault(result.category, {})
            category_dict[result.name] = {
                "url": result.url,
                "result": result.exists,
                "status_code": result.status_code,
                "error": result.error
            }

        return grouped

    @staticmethod
    def _print_results(results: Dict[str, Dict[str, Dict[str, Dict[str, object]]]]) -> None:
        """
        Pretty-print grouped results to the console.

        :param results: Grouped dictionary of results.
        """
        for version, categories in results.items():
            print(f"\n[bold magenta]>>> Version: {version}[/bold magenta]")

            for category, items in categories.items():
                print(f"[bold cyan]=== {category.upper()} ===[/bold cyan]")

                for name, info in items.items():
                    if info["result"] is True:
                        status = "[green]✅ Exists[/green]"
                    elif info["result"] is False:
                        status = "[red]❌ Not Found[/red]"
                    else:
                        error_msg = info.get("error", "Unknown error")
                        status = f"[red]⚠️ Error: {error_msg}[/]"

                    status_code = info.get("status_code")
                    status_info = f" (HTTP {status_code})" if status_code else ""

                    print(f"[yellow]{name}[/yellow]: {status}{status_info} -> {info['url']}")

    @staticmethod
    def _print_summary(results: List[URLCheckResult]) -> None:
        """
        Print a summary of total, found, not found, and errors.

        :param results: List of URLCheckResult objects.
        """
        print("\n[bold]Summary:[/bold]")
        print(f"Total URLs checked: {len(results)}")
        print(f"[green]Found: {sum(1 for r in results if r.exists is True)}[/green]")
        print(f"[red]Not found: {sum(1 for r in results if r.exists is False)}[/red]")
        print(f"[yellow]Errors: {sum(1 for r in results if r.exists is None)}[/yellow]")
