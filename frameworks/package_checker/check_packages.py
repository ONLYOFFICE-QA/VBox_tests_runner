# -*- coding: utf-8 -*-
from os.path import join, dirname, realpath
from dataclasses import dataclass, asdict

from host_tools import File
from host_tools.utils import Str
from rich import print

import aiohttp
from aiohttp import ClientSession
import asyncio
from typing import Dict, List, Union

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
    exists: bool

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
    ) -> List[URLCheckParams]:
        params_list = []

        for category, templates in self.templates.items():
            if categories and category not in categories:
                continue

            for name, tpl in templates.items():
                if names and name not in names:
                    continue

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

        return params_list

    async def check_urls(
            self,
            categories: List[str] = None,
            names: List[str] = None
    ) -> List[URLCheckResult]:
        tasks = []

        async with aiohttp.ClientSession() as session:
            for version in self.versions:
                params_list = self.generate_urls(version, categories=categories, names=names)
                for param in params_list:
                    tasks.append(self._check_url(session, param))

            return await asyncio.gather(*tasks)

    def run(
            self,
            categories: List[str] = None,
            names: List[str] = None,
            stdout: bool = True
    ) -> Dict[str, Dict[str, Dict[str, Dict[str, object]]]]:
        results = asyncio.run(self.check_urls(categories=categories, names=names))
        grouped = self._build_grouped_results(results=results)
        if stdout:
            self._print_results(results=grouped)

        return grouped

    @staticmethod
    def _build_grouped_results(results: List[URLCheckResult]) -> Dict[str, Dict[str, Dict[str, Dict[str, object]]]]:
        grouped: Dict[str, Dict[str, Dict[str, Dict[str, object]]]] = {}
        for result in results:
            grouped \
                .setdefault(result.version, {}) \
                .setdefault(result.category, {})[result.name] = {
                "url": result.url,
                "result": result.exists
            }
        return grouped

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
    async def _check_url(session: ClientSession, param: URLCheckParams) -> URLCheckResult:
        try:
            async with session.head(param.url, timeout=5) as response:
                exists = response.status == 200
        except Exception as e:
            print(f"[red]|ERROR| Exception while checking {param.url}: {e}")
            exists = None

        return URLCheckResult(**param.__dict__, exists=exists)
