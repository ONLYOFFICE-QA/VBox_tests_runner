# -*- coding: utf-8 -*-
from os.path import join, dirname, realpath
from dataclasses import dataclass
from typing import Dict, List, Union, Optional
import asyncio
import logging
from contextlib import asynccontextmanager, nullcontext

import aiohttp
from aiohttp import ClientSession, ClientTimeout, ClientConnectorError
from rich import print

from host_tools import File
from host_tools.utils import Str
from .config import Config
from ..VersionHandler import VersionHandler


@dataclass
class URLCheckParams:
    version: str
    category: str
    name: str
    url: str


@dataclass
class URLCheckResult:
    version: str
    category: str
    name: str
    url: str
    exists: Optional[bool]
    status_code: Optional[int] = None
    error: Optional[str] = None


class PackageURLChecker:
    """Async URL checker for package versions with improved error handling and performance."""

    def __init__(
            self,
            versions: Union[str, VersionHandler, List[Union[str, VersionHandler]]],
            template_path: Optional[str] = None,
            max_concurrent: int = None,
            timeout: int = 10,
            max_retries: int = 2
    ):
        self.config = Config()
        self.host = Str.delete_last_slash(self.config.host)
        self.template_path = template_path or join(dirname(realpath(__file__)), "templates.json")
        self.templates = File.read_json(self.template_path)
        self.versions: List[VersionHandler] = self._get_versions(versions)

        # Performance and reliability settings
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent else nullcontext()

        # Setup logging
        self.logger = logging.getLogger(__name__)

    async def find_latest_valid_version_with_all_packages(
            self,
            base_version: str,
            max_builds: int = 100,
            categories: Optional[List[str]] = None,
            names: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Checks the last few builds and returns the most recent version
        in which all packages exist (HTTP 200).

        :param base_version: Version without build number, e.g. "8.0.0"
        :param max_builds: Number of builds to check, starting from the latest
        :param categories: Optional list of categories to filter
        :param names: Optional list of package names to filter
        :return: The latest valid version string or None if not found
        """
        for build_number in reversed(range(max_builds)):
            version_str = f"{base_version}.{build_number}"
            version = VersionHandler(version=version_str)
            self.versions = [version]

            results = await self.check_urls(categories=categories, names=names)

            if all(r.exists is True for r in results):
                print(f"[green]✅ All packages found in version {version_str}[/green]")
                return version_str
            else:
                print(f"[dim]❌ Not all packages found in version {version_str}[/dim]")

        print(f"[red]❗ No version found with all required packages in the last {max_builds} builds[/red]")
        return None

    @staticmethod
    def _get_versions(
            versions: Union[str, VersionHandler, List[Union[str, VersionHandler]]]
    ) -> List[VersionHandler]:
        """Convert input versions to list of VersionHandler objects."""
        if not isinstance(versions, list):
            versions = [versions]
        return [v if isinstance(v, VersionHandler) else VersionHandler(version=v) for v in versions]

    def generate_urls(
            self,
            version: VersionHandler,
            categories: Optional[List[str]] = None,
            names: Optional[List[str]] = None
    ) -> List[URLCheckParams]:
        """Generate URL check parameters for given version and filters."""
        params_list = []

        for category, templates in self.templates.items():
            if categories and category not in categories:
                continue

            for name, tpl in templates.items():
                if names and name not in names:
                    continue

                try:
                    url = tpl.format(
                        host=self.host,
                        version=version.without_build,
                        build=version.build
                    )
                    params_list.append(URLCheckParams(
                        version=str(version),
                        category=category,
                        name=name,
                        url=url
                    ))
                except KeyError as e:
                    self.logger.warning(f"Template formatting error for {category}.{name}: {e}")
                    continue

        return params_list

    @asynccontextmanager
    async def _get_session(self):
        """Create optimized aiohttp session with proper configuration."""
        timeout = ClientTimeout(total=self.timeout, connect=5)
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=20,  # Max connections per host
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )

        async with ClientSession(
                timeout=timeout,
                connector=connector,
                headers={'User-Agent': 'PackageURLChecker/1.0'}
        ) as session:
            yield session

    async def check_urls(
            self,
            categories: Optional[List[str]] = None,
            names: Optional[List[str]] = None
    ) -> List[URLCheckResult]:
        """Check URLs asynchronously with proper session management."""
        tasks = []

        async with self._get_session() as session:
            for version in self.versions:
                params_list = self.generate_urls(version, categories=categories, names=names)
                for param in params_list:
                    tasks.append(self._check_url_with_retry(session, param))

            # Process with progress tracking if many URLs
            if len(tasks) > 100:
                return await self._check_urls_with_progress(tasks)
            else:
                return await asyncio.gather(*tasks, return_exceptions=False)

    @staticmethod
    async def _check_urls_with_progress(tasks: List) -> List[URLCheckResult]:
        """Process URLs in batches with progress indication."""
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
        """Check URL with retry logic and semaphore limiting."""
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
        """Check single URL with improved error handling."""
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

    def run(
            self,
            categories: Optional[List[str]] = None,
            names: Optional[List[str]] = None,
            stdout: bool = True
    ) -> Dict[str, Dict[str, Dict[str, Dict[str, object]]]]:
        """Run URL checks and return grouped results."""
        try:
            results = asyncio.run(self.check_urls(categories=categories, names=names))
            grouped = self._build_grouped_results(results)

            if stdout:
                self._print_results(grouped)
                self._print_summary(results)

            return grouped
        except Exception as e:
            self.logger.error(f"Error during URL checking: {e}")
            raise

    @staticmethod
    def _build_grouped_results(results: List[URLCheckResult]) -> Dict[str, Dict[str, Dict[str, Dict[str, object]]]]:
        """Build nested dictionary structure from results."""
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
        """Print formatted results with rich styling."""
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
        """Print summary statistics."""
        total = len(results)
        exists = sum(1 for r in results if r.exists is True)
        not_found = sum(1 for r in results if r.exists is False)
        errors = sum(1 for r in results if r.exists is None)

        print(f"\n[bold]Summary:[/bold]")
        print(f"Total URLs checked: {total}")
        print(f"[green]Found: {exists}[/green]")
        print(f"[red]Not found: {not_found}[/red]")
        print(f"[yellow]Errors: {errors}[/yellow]")

    def get_failed_urls(self, results: Optional[List[URLCheckResult]] = None) -> List[URLCheckResult]:
        """Get list of failed URL checks for debugging."""
        if results is None:
            results = asyncio.run(self.check_urls())

        return [r for r in results if r.exists is not True]