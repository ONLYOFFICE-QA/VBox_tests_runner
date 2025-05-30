# -*- coding: utf-8 -*-
from os.path import join, dirname, realpath

from host_tools import File
from host_tools.utils import Str
from rich import print

import aiohttp
from aiohttp import ClientSession
import asyncio
from typing import Dict, Tuple, List, Union

from .config import Config
from ..VersionHandler import VersionHandler


class PackageURLChecker:

    def __init__(self, versions: Union[str, VersionHandler, List[Union[str, VersionHandler]]], template_path: str = None):
        self.config = Config()
        self.host = Str.delete_last_slash(self.config.host)
        self.template_path = template_path or join(dirname(realpath(__file__)), "templates.json")
        self.templates = File.read_json(self.template_path)
        self.versions: List[VersionHandler] = self._get_versions(versions)

    @staticmethod
    def _get_versions(
            versions: Union[str, VersionHandler, List[Union[str, VersionHandler]]]
    ) -> List[VersionHandler]:
        if not isinstance(versions, list):
            versions = [versions]

        return [v if isinstance(v, VersionHandler) else VersionHandler(version=v) for v in versions]

    def generate_urls(
        self,
        version: VersionHandler,
        categories: List[str] = None,
        names: List[str] = None
    ) -> Dict[str, Dict[str, str]]:
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
                    version=version.without_build,
                    build=version.build
                )
                filtered_urls[name] = url

            if filtered_urls:
                urls_by_category[category] = filtered_urls

        return urls_by_category

    async def check_urls(
            self,
            categories: List[str] = None,
            names: List[str] = None
    ) -> List[Tuple[str, str, str, str, bool]]:
        """
        :return: List of (version, category, name, url, exists)
        """
        tasks = []

        async with aiohttp.ClientSession() as session:
            for version in self.versions:
                urls_by_category = self.generate_urls(version, categories=categories, names=names)
                for category, urls in urls_by_category.items():
                    for name, url in urls.items():
                        tasks.append(self._check_url(session, str(version), category, name, url))

            return await asyncio.gather(*tasks)

    def run(
            self,
            categories: List[str] = None,
            names: List[str] = None,
            stdout: bool = True
    ) -> Dict[str, Dict[str, Dict[str, Dict[str, object]]]]:
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
    def all_exist(grouped_results: Dict[str, Dict[str, Dict[str, Dict[str, object]]]]) -> bool:
        return all(
            info["result"]
            for version_data in grouped_results.values()
            for category_data in version_data.values()
            for info in category_data.values()
        )

    @staticmethod
    def _print_results(results: Dict[str, Dict[str, Dict[str, Dict[str, object]]]]) -> None:
        for version, categories in results.items():
            print(f"\n[bold magenta]>>> Version: {version}[/bold magenta]")
            for category, items in categories.items():
                print(f"[bold cyan]=== {category.upper()} ===[/bold cyan]")
                for name, info in items.items():
                    status = "[green]✅ Exists[/green]" if info["result"] else "[red]❌ Not Found[/red]"
                    print(f"[yellow]{name}[/yellow]: {status} -> {info['url']}")

    @staticmethod
    def _build_grouped_results(results: List[Tuple[str, str, str, str, bool]]) -> Dict[str, Dict[str, Dict[str, Dict[str, object]]]]:
        """
        :param results: (version, category, name, url, exists)
        :return: {version: {category: {name: {"url": ..., "result": ...}}}}
        """
        grouped: Dict[str, Dict[str, Dict[str, Dict[str, object]]]] = {}
        for version, category, name, url, exists in results:
            grouped.setdefault(version, {}).setdefault(category, {})[name] = {
                "url": url,
                "result": exists
            }
        return grouped

    @staticmethod
    async def _check_url(session: ClientSession, version: str, category: str, name: str, url: str) -> Tuple[str, str, str, str, bool]:
        try:
            async with session.head(url, timeout=5) as response:
                return version, category, name, url, response.status == 200
        except Exception as e:
            print(f"[red]|ERROR| Exception while checking {url}: {e}")
            return version, category, name, url, False
