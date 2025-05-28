# -*- coding: utf-8 -*-
from os.path import join, dirname, realpath

from host_tools import File
from host_tools.utils import Str
from rich import print

import aiohttp
from aiohttp import ClientSession
import asyncio
from typing import Dict, Tuple, List, Optional

from .config import Config
from .report import Report
from ..VersionHandler import VersionHandler


class PackageURLChecker:
    """
    Asynchronous checker for verifying existence of software package URLs based on templates.
    Templates are grouped by category (e.g., installers, builders, cores) in a JSON file.
    """

    def __init__(self, version: VersionHandler | str, template_path: str = None):
        """
        Initialize the URL checker.

        :param template_path: Path to the JSON file with categorized URL templates.
        :param version: Product version string (e.g., "9.0.0").
        :param build: Build number string (e.g., "122").
        """
        self.config = Config()
        self.host = Str.delete_last_slash(self.config.host)
        self.template_path = template_path or join(dirname(realpath(__file__)), "templates.json")
        self.version = version if isinstance(version, VersionHandler) else VersionHandler(version=version)
        self.templates = File.read_json(self.template_path)
        self.report = Report(version=str(self.version))

    def generate_urls(self) -> Dict[str, Dict[str, str]]:
        """
        Generate formatted URLs for all categories and names.

        :return: Dictionary of categories with name-URL mappings.
        """
        urls_by_category = {}
        for category, templates in self.templates.items():
            urls_by_category[category] = {
                name: tpl.format(host=self.host, version=self.version.without_build, build=self.version.build)
                for name, tpl in templates.items()
            }
        return urls_by_category

    @staticmethod
    async def check_url(session: ClientSession, category: str, name: str, url: str) -> Tuple[str, str, str, bool]:
        """
        Asynchronously check if a URL exists by sending a HEAD request.

        :param session: The aiohttp client session to use.
        :param category: The category of the template (e.g., installers, builders).
        :param name: The name of the template within the category.
        :param url: The fully generated URL to check.
        :return: Tuple of category, name, URL, and existence status (True if exists).
        """
        try:
            async with session.head(url, timeout=5) as response:
                return category, name, url, response.status == 200
        except Exception as e:
            print(f"[red]|ERROR| Exceptions occurred while checking {url}: {e}")
            return category, name, url, False

    async def check_all_urls(
            self,
            categories: List[str] = None,
            names: List[str] = None
    ) -> List[Tuple[str, str, str, bool]]:
        """
        Asynchronously check only selected categories or specific names of URLs.

        :param categories: List of category names to include (e.g., ["desktop", "core"]).
        :param names: List of specific name keys to include (e.g., ["debian", "win-64"]).
        :return: List of tuples (category, name, URL, result).
        """
        urls_by_category = self.generate_urls()
        filtered_tasks = []

        async with aiohttp.ClientSession() as session:
            for category, urls in urls_by_category.items():
                if categories and category not in categories:
                    continue
                for name, url in urls.items():
                    if names and name not in names:
                        continue
                    filtered_tasks.append(
                        self.check_url(session, category, name, url)
                    )

            return await asyncio.gather(*filtered_tasks)
        return None

    def run(
            self,
            categories: List[str] = None,
            names: List[str] = None,
            stdout: bool = True
    ) -> Dict[str, Dict[str, Dict[str, object]]]:
        """
        Run the checker and print results. Optionally filter by categories or names.

        :param stdout: Output the results to the console.
        :param categories: List of category names to check.
        :param names: List of specific name keys to check.
        :return: Grouped results dictionary.
        """
        if self.report.has_cache(categories, names):
            if stdout:
                print("Loaded results from CSV cache:")
            grouped_results = self.report.load_results(categories, names)
        else:
            if stdout:
                print("No cached results found, running checks...")
            results = asyncio.run(self.check_all_urls(categories=categories, names=names))
            grouped_results = self.build_grouped_results(results)
            self.report.save_results(grouped_results)

        if stdout:
            self.print_results(grouped_results)

        return grouped_results

    @staticmethod
    def print_results(grouped_results: Dict[str, Dict[str, Dict[str, object]]]) -> None:
        """
        Print the grouped URL check results to the console.

        :param grouped_results: Nested dictionary of results as built by build_grouped_results.
        """
        for category, entries in grouped_results.items():
            print(f"\n=== {category.upper()} ===")
            for name, info in entries.items():
                status = "✅ Exists" if info["result"] else "❌ Not Found"
                print(f"[{name}] {info['url']} -> {status}")

    @staticmethod
    def build_grouped_results(results: List[Tuple[str, str, str, bool]]) -> Dict[str, Dict[str, Dict[str, object]]]:
        """
        Build a nested result dictionary from the list of URL check results.

        :param results: List of tuples (category, name, url, result).
        :return: Nested dictionary {category: {name: {'url': ..., 'result': True/False}}}
        """
        grouped_results: Dict[str, Dict[str, Dict[str, object]]] = {}

        for category, name, url, exists in results:
            if category not in grouped_results:
                grouped_results[category] = {}
            grouped_results[category][name] = {
                "url": url,
                "result": exists
            }

        return grouped_results
