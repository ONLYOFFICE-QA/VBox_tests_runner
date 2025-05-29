# -*- coding: utf-8 -*-
from os.path import join, dirname, realpath

from host_tools import File
from host_tools.utils import Str
from rich import print

import aiohttp
from aiohttp import ClientSession
import asyncio
from typing import Dict, Tuple, List

from .config import Config
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

    def generate_urls(self, categories: List[str] = None, names: List[str] = None) -> Dict[str, Dict[str, str]]:
        """
        Generate and optionally filter formatted URLs by category and name.

        :param categories: List of category names to include.
        :param names: List of name keys to include.
        :return: Dictionary of filtered URLs {category: {name: url}}.
        """
        urls_by_category = {}

        for category, templates in self.templates.items():
            if categories and category not in categories:
                continue

            filtered_urls = {}
            for name, tpl in templates.items():
                if names and name not in names:
                    continue

                url = tpl.format(
                    host=self.host,
                    version=self.version.without_build,
                    build=self.version.build
                )
                filtered_urls[name] = url

            if filtered_urls:
                urls_by_category[category] = filtered_urls

        return urls_by_category

    async def check_urls(
            self,
            categories: List[str] = None,
            names: List[str] = None
    ) -> List[Tuple[str, str, str, bool]]:
        """
        Asynchronously check selected URLs.

        :param categories: Filter by categories.
        :param names: Filter by template names.
        :return: List of (category, name, url, exists).
        """
        urls_by_category = self.generate_urls(categories=categories, names=names)
        tasks = []

        async with aiohttp.ClientSession() as session:
            for category, urls in urls_by_category.items():
                for name, url in urls.items():
                    tasks.append(self._check_url(session, category, name, url))

            return await asyncio.gather(*tasks)

    def run(self, categories: List[str] = None, names: List[str] = None, stdout: bool = True) -> Dict[
        str, Dict[str, Dict[str, object]]]:
        """
        Run the asynchronous URL checker and return grouped results.

        :param categories: Optional list of categories to check.
        :param names: Optional list of names to check.
        :param stdout: If True, print the results to the console.
        :return: Grouped result dictionary.
        """
        results = asyncio.run(self.check_urls(categories=categories, names=names))
        grouped = self._build_grouped_results(results)

        if stdout:
            self._print_results(grouped)
            if self.all_exist(grouped):
                print("[bold green]✅ All URLs are valid.[/bold green]")
            else:
                print("[bold red]❌ Some URLs are missing.[/bold red]")

        return grouped

    @staticmethod
    def all_exist(grouped_results: Dict[str, Dict[str, Dict[str, object]]]) -> bool:
        """
        Check if all URLs in the grouped results exist.

        :param grouped_results: Grouped results from `build_grouped_results`.
        :return: True if all URLs returned True in 'result', else False.
        """
        return all(
            info["result"]
            for category in grouped_results.values()
            for info in category.values()
        )

    @staticmethod
    def _print_results(results: Dict[str, Dict[str, Dict[str, object]]]) -> None:
        """
        Print the grouped URL check results.

        :param results: Dictionary structured as {category: {name: {"url": str, "result": bool}}}
        """
        for category, items in results.items():
            print(f"\n[bold cyan]=== {category.upper()} ===[/bold cyan]")
            for name, info in items.items():
                status = "[green]✅ Exists[/green]" if info["result"] else "[red]❌ Not Found[/red]"
                print(f"[yellow]{name}[/yellow]: {status} -> {info['url']}")

    @staticmethod
    def _build_grouped_results(results: List[Tuple[str, str, str, bool]]) -> Dict[str, Dict[str, Dict[str, object]]]:
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

    @staticmethod
    async def _check_url(session: ClientSession, category: str, name: str, url: str) -> Tuple[str, str, str, bool]:
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

